# loutilities — Claude Code Guide

## Project Overview

Python utility library providing shared helpers for Lou King's Flask/SQLAlchemy web applications (e.g., louking/contracts, louking/tm-csv-connector).

- GitHub: https://github.com/louking/loutilities
- Version: `loutilities/version.py`

## Environment

- **Python/pip**: `venv/Scripts/python.exe` / `venv/Scripts/pip`
- **Python version**: 3.9 (venv)
- **Key dependencies**: Flask 2.2, SQLAlchemy 2.x, Flask-Security-Too 5.x, Flask-SQLAlchemy 3.x

## Running Tests

pytest is not installed in the venv. Install it before running tests:

```bash
venv/Scripts/pip install pytest faker
venv/Scripts/python -m pytest tests/
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
