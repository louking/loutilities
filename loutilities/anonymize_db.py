#!/usr/bin/env python
"""
anonymize_db.py - anonymize PII fields in mysqldump files

Reads one or more mysqldump SQL files and replaces configured PII columns with
synthetic values, leaving all other data intact. Processes files sequentially so
that sync relationships (e.g. localuser mirrors user) are resolved correctly —
pass the users DB dump before the members DB dump.

Each app supplies its own YAML config describing which tables and columns to
scrub; the script itself contains no app-specific logic.

Usage:
    # Single file to stdout:
    anonymize_db -c anonymize_members.yaml users.sql > users_anon.sql

    # Multiple files to an output directory (same filenames):
    anonymize_db -c anonymize_members.yaml --output-dir ./anon/ users.sql members.sql
"""

import argparse
import os
import random
import re
import sys
from datetime import date, timedelta

import yaml


# ---------------------------------------------------------------------------
# SQL value tokenizer
# ---------------------------------------------------------------------------

def _split_insert_rows(values_str):
    """
    Split the VALUES clause of an INSERT statement into per-row content strings
    (without the surrounding parentheses). Handles strings containing commas
    and parentheses correctly.
    """
    rows = []
    i = 0
    n = len(values_str)

    while i < n:
        # Advance to opening paren of next row
        while i < n and values_str[i] != '(':
            i += 1
        if i >= n:
            break

        i += 1          # skip '('
        start = i
        depth = 1

        while i < n and depth > 0:
            c = values_str[i]
            if c == "'":                        # string literal
                i += 1
                while i < n:
                    if values_str[i] == '\\':
                        i += 2                  # skip escape sequence
                    elif values_str[i] == "'":
                        i += 1
                        break
                    else:
                        i += 1
            elif c == '(':
                depth += 1
                i += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    rows.append(values_str[start:i])
                    i += 1                      # skip ')'
                else:
                    i += 1
            else:
                i += 1

    return rows


def _tokenize_row(s):
    """
    Split a row's value string (content between the outer parens) into a list
    of raw SQL tokens, one per column. Tokens preserve original quoting so
    un-modified columns are written back verbatim.
    """
    tokens = []
    i = 0
    n = len(s)

    while i < n:
        while i < n and s[i] in ' \t':
            i += 1
        if i >= n:
            break

        start = i

        if s[i] == "'":
            # String literal — scan to closing unescaped quote
            i += 1
            while i < n:
                if s[i] == '\\':
                    i += 2
                elif s[i] == "'":
                    i += 1
                    break
                else:
                    i += 1
            token = s[start:i]
        elif s[i:i+4] == 'NULL' and (i + 4 >= n or s[i + 4] in (',', ' ', '\t')):
            token = 'NULL'
            i += 4
        elif s[i] == '0' and i + 1 < n and s[i + 1] in 'xX':
            # Hex literal
            i += 2
            while i < n and s[i] in '0123456789abcdefABCDEF':
                i += 1
            token = s[start:i]
        else:
            # Unquoted number or other literal
            while i < n and s[i] not in (',', ' ', '\t'):
                i += 1
            token = s[start:i]

        tokens.append(token)

        while i < n and s[i] in ' \t':
            i += 1
        if i < n and s[i] == ',':
            i += 1

    return tokens


def _sql_to_python(token):
    """Convert a raw SQL token to a Python string, or None for NULL."""
    if token == 'NULL':
        return None
    if token.startswith("'") and token.endswith("'"):
        s = token[1:-1]
        result = []
        i = 0
        escape_map = {
            'n': '\n', 'r': '\r', 't': '\t', '0': '\0',
            "'": "'", '\\': '\\', '"': '"', 'b': '\b', 'Z': '\x1a',
        }
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                result.append(escape_map.get(s[i + 1], s[i + 1]))
                i += 2
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)
    return token     # number or hex literal — return as-is


def _python_to_sql(value):
    """Convert a Python string (or None) to a SQL token."""
    if value is None:
        return 'NULL'
    s = (str(value)
         .replace('\\', '\\\\')
         .replace("'", "\\'")
         .replace('\n', '\\n')
         .replace('\r', '\\r')
         .replace('\t', '\\t')
         .replace('\0', '\\0'))
    return f"'{s}'"


# ---------------------------------------------------------------------------
# Anonymization generators
# ---------------------------------------------------------------------------

def _anon_email(row_id):
    return f'user{row_id}@example.com'


def _anon_fullname(row_id):
    return f'Firstname{row_id} Lastname{row_id}'


def _anon_firstname(row_id):
    return f'Firstname{row_id}'


def _anon_lastname(row_id):
    return f'Lastname{row_id}'


def _anon_date_shift(date_str, row_id):
    """Shift a date by a deterministic random offset seeded on row_id."""
    if date_str is None:
        return None
    try:
        d = date.fromisoformat(date_str)
        rng = random.Random(int(row_id) * 97 + 31337)
        d = d + timedelta(days=rng.randint(-1095, 1095))   # ±3 years
        return str(d)
    except (ValueError, TypeError, AttributeError):
        return date_str


# Map type name → lambda(row_id, original_python_value) → new python value
_GENERATORS = {
    'email':      lambda rid, _v: _anon_email(rid),
    'fullname':   lambda rid, _v: _anon_fullname(rid),
    'firstname':  lambda rid, _v: _anon_firstname(rid),
    'lastname':   lambda rid, _v: _anon_lastname(rid),
    'date_shift': lambda rid,  v: _anon_date_shift(v, rid),
    'ip':         lambda _r,  _v: '127.0.0.1',
    'text':       lambda _r,  _v: 'anonymized',
    'city':       lambda _r,  _v: 'Anytown',
}


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

_CREATE_TABLE_RE = re.compile(r'^CREATE TABLE `(\w+)`')
_COLUMN_DEF_RE   = re.compile(r'^\s+`(\w+)`\s')


class DumpAnonymizer:
    """Stream-processes mysqldump files, replacing configured PII columns."""

    def __init__(self, config):
        self._tables_cfg = config.get('tables', {})
        self._table_columns = {}        # table_name -> [col, ...]
        # sync_maps[source_table][source_pk_value] = {field_name: anon_value}
        self._sync_maps = {}

        # Precompute which fields of which tables need to be stored for sync
        # sync_sources[source_table] = {source_field, ...}
        self._sync_sources = {}
        for _tgt, tgt_cfg in self._tables_cfg.items():
            for field, fcfg in tgt_cfg.get('fields', {}).items():
                if fcfg.get('type') == 'sync':
                    src_table = fcfg['source_table']
                    src_field = fcfg.get('source_field', field)
                    self._sync_sources.setdefault(src_table, set()).add(src_field)

    # ------------------------------------------------------------------
    # CREATE TABLE parsing
    # ------------------------------------------------------------------

    def _parse_create_table(self, block):
        """Return (table_name, [col_name, ...]) from a buffered CREATE TABLE block."""
        first_line = block.split('\n')[0]
        m = _CREATE_TABLE_RE.match(first_line)
        if not m:
            return None, []
        table_name = m.group(1)
        columns = []
        for line in block.split('\n')[1:]:
            stripped = line.strip()
            # Skip constraint lines and the closing ) line
            if not stripped or any(stripped.startswith(kw) for kw in
                                   ('PRIMARY', 'KEY', 'UNIQUE', 'CONSTRAINT', ')', 'CHECK')):
                continue
            cm = _COLUMN_DEF_RE.match(line)
            if cm:
                columns.append(cm.group(1))
        return table_name, columns

    # ------------------------------------------------------------------
    # Value generation
    # ------------------------------------------------------------------

    def _generate(self, field_cfg, row_id, original_val, columns, tokens):
        """
        Compute the anonymized Python value for one field.
        Returns the original value unchanged if the type is unknown.
        """
        ftype = field_cfg.get('type', 'text')

        # NULL preservation: keep NULL for every type except 'fixed'
        if original_val is None and ftype not in ('fixed', 'sync'):
            return None

        if ftype == 'sync':
            src_table  = field_cfg['source_table']
            src_field  = field_cfg.get('source_field')   # caller sets this
            join_field = field_cfg['join_field']

            join_val = None
            if join_field in columns:
                join_val = _sql_to_python(tokens[columns.index(join_field)])

            return (self._sync_maps
                    .get(src_table, {})
                    .get(join_val, {})
                    .get(src_field, original_val))

        if ftype == 'fixed':
            return field_cfg.get('value', 'anonymized')

        generator = _GENERATORS.get(ftype)
        if generator is None:
            return original_val

        try:
            rid = int(row_id) if row_id is not None else 0
        except (ValueError, TypeError):
            rid = abs(hash(str(row_id))) % 1_000_000

        return generator(rid, original_val)

    # ------------------------------------------------------------------
    # Sync map population
    # ------------------------------------------------------------------

    def _populate_sync_map(self, table_name, columns, row_id, tokens):
        """
        If table_name is a sync source, compute and store the anonymized
        values for fields that downstream tables will need.
        """
        needed_fields = self._sync_sources.get(table_name)
        if not needed_fields:
            return

        table_cfg  = self._tables_cfg.get(table_name, {})
        fields_cfg = table_cfg.get('fields', {})

        for src_field in needed_fields:
            fcfg = fields_cfg.get(src_field)
            if not fcfg or src_field not in columns:
                continue
            original_val = _sql_to_python(tokens[columns.index(src_field)])
            anon_val = self._generate(fcfg, row_id, original_val, columns, tokens)

            (self._sync_maps
             .setdefault(table_name, {})
             .setdefault(row_id, {})[src_field]) = anon_val

    # ------------------------------------------------------------------
    # Row anonymization
    # ------------------------------------------------------------------

    def _anonymize_row(self, table_name, columns, tokens):
        """Return a new token list with PII columns replaced."""
        table_cfg  = self._tables_cfg.get(table_name, {})
        fields_cfg = table_cfg.get('fields', {})
        if not fields_cfg:
            return tokens

        # Row primary key for deterministic value generation
        pk_field = table_cfg.get('pk', 'id')
        row_id   = None
        if pk_field in columns:
            row_id = _sql_to_python(tokens[columns.index(pk_field)])

        # Store sync values before modifying tokens
        self._populate_sync_map(table_name, columns, row_id, tokens)

        result = list(tokens)
        for field_name, fcfg in fields_cfg.items():
            if field_name not in columns:
                continue
            idx          = columns.index(field_name)
            original_val = _sql_to_python(tokens[idx])

            # For sync fields, inject source_field so _generate can look it up
            if fcfg.get('type') == 'sync' and 'source_field' not in fcfg:
                fcfg = dict(fcfg, source_field=field_name)

            anon_val = self._generate(fcfg, row_id, original_val, columns, tokens)

            if anon_val is None:
                result[idx] = 'NULL'
            elif anon_val != original_val:
                result[idx] = _python_to_sql(str(anon_val))

        return result

    # ------------------------------------------------------------------
    # INSERT line processing
    # ------------------------------------------------------------------

    def _process_insert(self, line):
        """Parse, anonymize, and re-serialise an INSERT line."""
        if not line.startswith('INSERT INTO `'):
            return line

        i          = 13                     # len('INSERT INTO `')
        j          = line.index('`', i)
        table_name = line[i:j]

        if table_name not in self._tables_cfg:
            return line

        rest = line[j + 1:].lstrip()       # text after closing backtick

        # Optional explicit column list: (col1, col2, ...)
        col_list_str = None
        if rest.startswith('('):
            col_end      = rest.index(')')
            col_list_str = rest[1:col_end]
            columns      = [c.strip().strip('`') for c in col_list_str.split(',')]
            rest         = rest[col_end + 1:].lstrip()
        else:
            columns = self._table_columns.get(table_name, [])

        if not columns:
            return line

        if not rest.upper().startswith('VALUES'):
            return line

        # Preserve output line format: detect newline between VALUES and first row
        values_tail = rest[6:]              # text after 'VALUES'
        multiline   = '\n' in values_tail.lstrip(' \t')
        rest        = values_tail.lstrip()  # strip whitespace including newline
        rest        = rest.rstrip()
        if rest.endswith(';'):
            rest = rest[:-1]

        row_strings = _split_insert_rows(rest)
        new_rows = []
        for row_str in row_strings:
            tokens = _tokenize_row(row_str)
            if len(tokens) != len(columns):
                # Column count mismatch — emit unchanged to avoid corruption
                new_rows.append(f'({row_str})')
            else:
                new_tokens = self._anonymize_row(table_name, columns, tokens)
                new_rows.append('(' + ','.join(new_tokens) + ')')

        if multiline:
            rows_str = ',\n'.join(new_rows)
            if col_list_str:
                return f'INSERT INTO `{table_name}` ({col_list_str}) VALUES\n{rows_str};\n'
            return f'INSERT INTO `{table_name}` VALUES\n{rows_str};\n'
        else:
            if col_list_str:
                return f'INSERT INTO `{table_name}` ({col_list_str}) VALUES {",".join(new_rows)};\n'
            return f'INSERT INTO `{table_name}` VALUES {",".join(new_rows)};\n'

    # ------------------------------------------------------------------
    # File processing
    # ------------------------------------------------------------------

    def process_file(self, infile, outfile):
        """Stream one mysqldump file from infile to outfile."""
        in_create       = False
        create_buffer   = []
        insert_buffer   = []    # multi-line INSERT that needs anonymizing
        insert_passthru = False # multi-line INSERT whose table is not in config

        for line in infile:
            # Multi-line INSERT — pass-through (table not in config)
            if insert_passthru:
                outfile.write(line)
                if line.rstrip('\n').rstrip().endswith(';'):
                    insert_passthru = False
                continue

            # Multi-line INSERT — buffer until terminating semicolon
            if insert_buffer:
                insert_buffer.append(line)
                if line.rstrip('\n').rstrip().endswith(';'):
                    outfile.write(self._process_insert(''.join(insert_buffer)))
                    insert_buffer = []
                continue

            # CREATE TABLE block
            if in_create:
                create_buffer.append(line.rstrip('\n'))
                outfile.write(line)
                if line.startswith(')'):
                    block = '\n'.join(create_buffer)
                    tname, cols = self._parse_create_table(block)
                    if tname and cols:
                        self._table_columns[tname] = cols
                    in_create     = False
                    create_buffer = []
                continue

            if _CREATE_TABLE_RE.match(line):
                in_create     = True
                create_buffer = [line.rstrip('\n')]
                outfile.write(line)
                continue

            # INSERT line
            if line.startswith('INSERT INTO `'):
                if line.rstrip('\n').rstrip().endswith(';'):
                    # Entire INSERT on one line
                    outfile.write(self._process_insert(line))
                else:
                    # Multi-line INSERT — peek at table name to choose mode
                    i = 13      # len('INSERT INTO `')
                    j = line.index('`', i)
                    if line[i:j] in self._tables_cfg:
                        insert_buffer = [line]
                    else:
                        insert_passthru = True
                        outfile.write(line)
                continue

            outfile.write(line)

    def process_files(self, file_pairs):
        """
        Process (input_path, output_path_or_None) pairs in order.
        Pass None as output_path to write to stdout.
        """
        for inpath, outpath in file_pairs:
            print(f'Processing {inpath} ...', file=sys.stderr)
            with open(inpath, 'r', encoding='utf-8', errors='replace') as inf:
                if outpath:
                    with open(outpath, 'w', encoding='utf-8') as outf:
                        self.process_file(inf, outf)
                    print(f'  -> {outpath}', file=sys.stderr)
                else:
                    self.process_file(inf, sys.stdout)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Anonymize PII fields in mysqldump files using a YAML config.',
        epilog=(
            'When using sync relationships (e.g. localuser mirrors user), '
            'pass the source DB dump first so the sync map is populated before '
            'the target DB dump is processed.'
        ),
    )
    parser.add_argument(
        '-c', '--config', required=True, metavar='CONFIG',
        help='YAML configuration file describing which tables/columns to anonymize',
    )
    parser.add_argument(
        '--output-dir', metavar='DIR',
        help='Write output files here, using the same filenames as the inputs. '
             'Required when more than one input file is given.',
    )
    parser.add_argument(
        'inputs', nargs='+', metavar='DUMP_FILE',
        help='Input mysqldump SQL file(s)',
    )
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    anonymizer = DumpAnonymizer(config)

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        file_pairs = [
            (inp, os.path.join(args.output_dir, os.path.basename(inp)))
            for inp in args.inputs
        ]
    else:
        if len(args.inputs) > 1:
            parser.error('Multiple input files require --output-dir.')
        file_pairs = [(args.inputs[0], None)]

    anonymizer.process_files(file_pairs)


if __name__ == '__main__':
    main()
