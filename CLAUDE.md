# enchilada

Local FHIR R4 terminology server backed by OMOP vocabularies. See README.md for full spec.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn enchilada.main:app --host 0.0.0.0 --port 8081 --reload
```

Or via config:

```bash
uv run python -m enchilada
```

## Test

```bash
uv run pytest
```

## Swagger UI

FastAPI auto-generates Swagger at `/docs` and ReDoc at `/redoc` — no extra setup needed.
FHIR operation names begin with `$` (e.g. `$translate`). The `$` is a legal URL character;
FastAPI routes and Swagger display it literally. Do not escape or encode it in route paths.

## Key constraints

- `CONCEPT_RELATIONSHIP.csv` is not available locally. The two-step translation path (step 3
  in README translation logic) must be coded but will not be exercised by tests until that
  file is provided. The server must start and handle requests correctly without it.
- Data files are large (7.4M rows). SQLite DB is built once from CSV on first run and reused.
  Do not rebuild it on every startup.
- The SQLite file path and CSV paths come from `config.yaml`, not environment variables.
- Do not add authentication, write endpoints, or any API surface beyond what README specifies.

## Project layout

```
enchilada/
    __main__.py       # reads config.yaml, starts uvicorn
    main.py           # FastAPI app, route registration
    db.py             # SQLite setup, CSV loading, index creation
    translate.py      # ConceptMap/$translate logic
    vocab.py          # FHIR URI → OMOP vocabulary_id mapping
config.yaml
tests/
    test_translate.py
```
