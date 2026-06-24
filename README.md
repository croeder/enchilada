# Enchilada Terminology Server
![Enchilada](enchilada-logo-card.png)

**[Documentation](https://croeder.github.io/enchilada/)**

A minimal, local FHIR R4/R5 terminology server implementing a subset of the standard FHIR terminology
API, backed by an on-disk copy of the OMOP vocabularies.  _It does not ship with any terminologies_. 
They need to be downloaded by prospective users.  
This implementation does not deal with rate limits, user registration, licenses or production-level volume. 
It is meant for local development or demonstration and adherence to the FHIR standards.

## Purpose

Matchbox calls an external FHIR terminology server to resolve source codes (SNOMED, ICD,
RxNorm, etc.) to OMOP concept IDs during `$transform` operations. This project provides a
local alternative for offline use, deterministic results, and no external network dependency.

## API surface

The FHIR R4/R5 terminology API defines six operations across three resource types. This project
implements the subset relevant to concept translation, exposed under both `/r4/` and `/r5/`
prefixes. The two versions share identical translate logic and response shapes; they differ only
in the `fhirVersion` field returned by `GET /rN/metadata`.

| Resource | Interactions | Operations |
|---|---|---|
| `ConceptMap` | read, search-type | **$translate** ← primary target |
| `CodeSystem` | read, search-type | lookup, validate-code, subsumes |
| `ValueSet` | read, search-type | expand, validate-code |

Not implemented: `ConceptMap/$closure` (transitive closure table for search-time subsumption).
All implemented operations are standard FHIR — no proprietary extensions.

Initial implementation focuses on `ConceptMap/$translate`. The others can be added
incrementally as needed.

### ConceptMap/$translate

```
POST /r4/ConceptMap/$translate
POST /r5/ConceptMap/$translate
```

Both endpoints accept and return the same FHIR Parameters resource format.

Parameters:
- `system` — source vocabulary URI (e.g. `http://snomed.info/sct`)
- `code` — source code (e.g. `38341003`)
- `targetsystem` — target vocabulary URI (e.g. `http://ohdsi.org/omop`)

**Match found** — HTTP 200:
```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "result", "valueBoolean": true },
    { "name": "match", "part": [
      { "name": "equivalence", "valueCode": "equivalent" },
      { "name": "concept", "valueCoding": {
        "system": "http://ohdsi.org/omop",
        "code": "316866"
      }}
    ]}
  ]
}
```

**No match found** — HTTP 200 (per FHIR spec; `$translate` is an operation returning a
result, not a resource lookup, so 404 does not apply):
```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "result", "valueBoolean": false },
    { "name": "message", "valueString": "No mapping found for SNOMED#38341003" }
  ]
}
```

The `message` parameter is defined in the FHIR spec as optional on both match and no-match;
here it is always populated on no-match to aid debugging.

## Data source

Both `CONCEPT.csv` and `CONCEPT_RELATIONSHIP.csv` must be downloaded from [Athena](https://athena.ohdsi.org).
Select these vocabulary bundles: **SNOMED, ICD10CM, ICD9CM, RxNorm, LOINC, CVX, UCUM, Race**.

`CONCEPT_RELATIONSHIP.csv` is required for translating non-standard source codes via the
`Maps to` relationship.

## Technology

- **Python + FastAPI** — minimal REST layer; one route handler per operation
- **SQLite** — point-lookup database loaded from CONCEPT.csv at startup; indexed on
  `(concept_code, vocabulary_id)`. SQLite is purpose-built for OLTP point lookups and
  a better fit than DuckDB (which is optimized for analytical scans, not single-row
  lookups over 7M rows). The CSV is loaded into a SQLite file once on first run;
  subsequent server starts reuse the existing file.

## Configuration

`config.yaml`:
```yaml
server:
  host: 0.0.0.0
  port: 8081

data:
  concept_csv: /data/CONCEPT.csv
  concept_relationship_csv: /data/CONCEPT_RELATIONSHIP.csv
  sqlite_db: ./enchilada.db        # created on first run, reused thereafter
```

Optional TLS — required when matchbox runs in Docker because HAPI's OkHttp client forces a
TLS handshake even for `http://` URLs. Omit these keys for plain-HTTP local development.

```yaml
server:
  ssl_certfile: /certs/enchilada.crt
  ssl_keyfile:  /certs/enchilada.key
```

Generate a self-signed cert and import it into a Java truststore (see `matchbox_scripts/certs/`):

```bash
openssl req -x509 -newkey rsa:2048 -keyout enchilada.key -out enchilada.crt \
  -days 3650 -nodes -subj "/CN=enchilada" \
  -addext "subjectAltName=DNS:enchilada,DNS:localhost,IP:127.0.0.1"

keytool -importcert -file enchilada.crt -keystore enchilada.jks \
  -storepass changeit -alias enchilada -noprompt
```

## Translation logic

For `ConceptMap/$translate` given `(system, code, targetsystem)`:

> **Known matchbox bug — system URI missing from $translate POST body**
>
> When an FML `translate()` call uses an empty ConceptMap URL (e.g. `translate(coding, '', 'code')`),
> matchbox sends a POST body with only `{"name":"code","valueCode":"..."}` — the `system` parameter
> is absent. This was observed empirically: the Coding variable `sc` in the FML pattern
> `src.code.coding first as sc -> tgt.field = translate(sc, '', 'code')` has its system URI stripped
> before the HTTP request is built. FHIR-compliant servers must return 400 if `system` is absent;
> echidna (public hosted server) accepts system-absent lookups as a courtesy.
>
> Enchilada works around this by falling back to a cross-vocabulary search over all standard concepts
> when `system` is absent. First match wins — unambiguous in practice given the Athena vocabulary set.
>
> **Upstream bug location**: `matchbox-engine/src/main/java/ch/ahdis/matchbox/mappinglanguage/`
> — either `MatchboxStructureMapUtilities.translate()` (the `getProperty("system",...)` call that
> reconstructs the Coding from the FML element-model variable) or `ConceptMapEngine.translateViaTxServer()`
> (the `source.hasSystem()` gate before adding system to the Parameters). Unit tests are in
> `TranslateCodingSystemTests.java` (class `WhenFmlUsesCodingFirstExtraction`). These tests isolate
> whether the system is dropped at the FML binding step or at the tx-server request step.

1. Map FHIR vocabulary URI → OMOP `vocabulary_id`:

| FHIR URI | OMOP vocabulary_id |
|---|---|
| `http://snomed.info/sct` | `SNOMED` |
| `http://hl7.org/fhir/sid/icd-10-cm` | `ICD10CM` |
| `http://hl7.org/fhir/sid/icd-9-cm` | `ICD9CM` |
| `http://www.nlm.nih.gov/research/umls/rxnorm` | `RxNorm` |
| `http://loinc.org` | `LOINC` |
| `http://hl7.org/fhir/sid/cvx` | `CVX` |

2. Query SQLite `CONCEPT` for `concept_code = code` AND `vocabulary_id = <mapped>` AND
   `standard_concept = 'S'` → return `concept_id` directly.

3. If not found as a standard concept, join through `CONCEPT_RELATIONSHIP` on
   `relationship_id = 'Maps to'` to find the standard concept (requires Athena download).

4. If still not found, return `result=false` with a descriptive `message`.

## Development

FastAPI serves a Swagger UI at `http://localhost:8081/docs` and ReDoc at
`http://localhost:8081/redoc`. Both are available automatically with no extra configuration.

FHIR operation paths use `$` (e.g. `/r4/ConceptMap/$translate`, `/r5/ConceptMap/$translate`).
The `$` is a valid URL character and FastAPI handles it without escaping; it appears literally
in the Swagger UI.

## Matchbox integration

Use the `/r4/` prefix when connecting a FHIR R4 matchbox instance, `/r5/` for R5.

Local development (plain HTTP):
```yaml
matchbox:
  fhir:
    context:
      txServer: http://localhost:8081/r4   # or /r5 for R5 matchbox
      translateMode: server
```

Docker (TLS required — HAPI forces TLS even on plain-http URLs):
```yaml
matchbox:
  fhir:
    context:
      txServer: https://enchilada:8081/r4   # or /r5 for R5 matchbox
      translateMode: fallback
```

Mount the Java truststore into matchbox and set:
```
JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/certs/enchilada.jks -Djavax.net.ssl.trustStorePassword=changeit
```

## Running as a Docker container

The published image is `croeder/enchilada:latest`. In normal use it runs as part of the
compose stack in `dqd_docker` — no standalone setup is needed. The compose file mounts
the vocabulary files and a persistent SQLite volume:

```yaml
enchilada:
  image: croeder/enchilada:latest
  ports:
    - "8081:8081"
  volumes:
    - enchilada-db:/db
    - ${CONCEPT_CSV:-./CONCEPT.csv}:/data/CONCEPT.csv:ro
    - ${CONCEPT_RELATIONSHIP_CSV:-./CONCEPT_RELATIONSHIP.csv}:/data/CONCEPT_RELATIONSHIP.csv:ro
```

Place `CONCEPT.csv` and `CONCEPT_RELATIONSHIP.csv` in your working directory before starting
(or set `CONCEPT_CSV` and `CONCEPT_RELATIONSHIP_CSV` environment variables to their paths).
The SQLite database is built from the CSVs on first run (~1–2 min) and cached in the
`enchilada-db` volume for subsequent starts.

enchilada serves over HTTPS with a self-signed certificate. The matchbox image includes a
combined JKS truststore that covers enchilada's cert, so no manual certificate setup is
required. See the [organization README](https://github.com/croeder-fhir-to-omop) for full
compose usage instructions.

## Out of scope

- Full OMOP vocabulary coverage beyond what's in the Athena download
- Authentication
- Write operations

## License

Licensed under the [Apache License 2.0](./LICENSE). Copyright 2026 Christophe Roeder.

enchilada serves OMOP vocabulary content loaded from Athena. Individual vocabularies carry their own license terms — see [NOTICES.md](https://github.com/croeder-fhir-to-omop/.github/blob/main/profile/NOTICES.md) for details.

See the [organization README](https://github.com/croeder-fhir-to-omop) for full pipeline documentation.
