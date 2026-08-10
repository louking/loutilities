# loutilities — Claude Code Guide

## Project Overview

Python utility library providing shared helpers for Lou King's Flask/SQLAlchemy web applications (e.g., louking/contracts, louking/tm-csv-connector).

- GitHub: https://github.com/louking/loutilities
- Version: `loutilities/version.py`

## Environment

- **Python/pip**: `.venv/bin/python` / `.venv/bin/pip`
- **Python version**: 3.14 (.venv)
- **Key dependencies**: Flask 3.x, SQLAlchemy 2.x, Flask-Security-Too 5.x, Flask-SQLAlchemy 3.x

## Running Tests

pytest is not installed in the venv by default. Install it before running tests:

```bash
.venv/bin/pip install pytest faker
.venv/bin/python -m pytest tests/
```

Tests use SQLite in-memory databases (`create_engine('sqlite://')`).

## Project Structure

```
loutilities/          # main package
  tables.py           # DataTables/Editor integration (largest module)
  sqlalchemy_helpers.py
  user/               # user management (flask-security-too)
  flask_helpers/      # blueprints, decorators, mailer
  flask/user/         # Flask user views
  tables-assets/      # static/template files to copy into consuming projects
  version.py          # single source of version truth
tests/                # unittest-based tests
  models.py           # shared SQLAlchemy test models
  test_sqlalchemy_helpers.py
  test_tables.py
```

## Versioning

Version is defined only in `loutilities/version.py`. Bump it there; `setup.py` reads it.

## Code Style

- Docstring at the top of each file
- Standard import order: standard → pypi → homegrown
- `debug = False` flag pattern used for optional debug logging

## DataTables Buttons/Editor Integration Gotcha

`get_button_options()` in `tables-assets/static/datatables.js` auto-attaches the shared `editor:` reference to a button **only when the button is passed as the literal string** `'create'`/`'edit'`/`'editRefresh'`/`'editChildRowRefresh'`/`'remove'`. A consuming app's Python `buttons=[...]` list often needs to override one of these standard actions with an object instead — e.g. `{'extend': 'create', 'enabled': False, 'attr': {'title': '...'}}` to render a conditionally-disabled create button. Passing that object form used to skip the `editor:` annotation entirely (it fell through to the plain pass-through `else` branch), leaving `config.editor === null` inside DataTables' own built-in `create`/`edit`/etc. button text functions (e.g. `config.editor.i18n(...)`) — a `Cannot read properties of null (reading 'i18n')` crash at DataTables Buttons init, not at click time, so the whole table failed to render.

**Fix**: `get_button_options()` now also checks object-form buttons for `extend` matching one of those same action names, and injects `editor:editor` unless the object already supplies its own `editor` (preserving the pattern used for a custom `extend: 'selected'` button bound to its own saeditor instance). Any consuming app extending a standard editor action with extra config (disabled state, custom text/attr, etc.) gets this for free — no need to pass `editor` explicitly unless intentionally binding to a different editor instance.
