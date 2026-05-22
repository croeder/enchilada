# enchilada

A local FHIR R4 terminology server implementing a subset of the standard FHIR terminology
API, backed by an on-disk copy of the OMOP vocabularies.

## Purpose

Matchbox calls an external FHIR terminology server to resolve source codes (SNOMED, ICD,
RxNorm, etc.) to OMOP concept IDs during `$transform` operations. This project provides a
local alternative for offline use, deterministic results, and no external network dependency.

## API surface

The FHIR R4 terminology API defines six operations across three resource types. This project
implements the subset relevant to concept translation:

| Resource | Interactions | Operations |
|---|---|---|
| `ConceptMap` | read, search-type | **$translate** ← primary target |
| `CodeSystem` | read, search-type | lookup, validate-code, subsumes |
| `ValueSet` | read, search-type | expand, validate-code |

Not implemented: `ConceptMap/$closure` (transitive closure table for search-time subsumption).
All implemented operations are standard FHIR R4 — no proprietary extensions.

Initial implementation focuses on `ConceptMap/$translate`. The others can be added
incrementally as needed.

### ConceptMap/$translate

```
POST /r4/ConceptMap/$translate
```

Parameters:
- `system` — source vocabulary URI (e.g. `http://snomed.info/sct`)
- `code` — source code (e.g. `38341003`)
- `targetsystem` — target vocabulary URI (e.g. `http://ohdsi.org/omop`)

Returns a standard FHIR `Parameters` resource:
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

## Data source

### CONCEPT.csv (available locally)

`/Users/croeder/git/CCDA/tislab-clad/CCDA_OMOP_Private/CONCEPT.csv`

- 7.4M rows, 965 MB
- Columns: `concept_id`, `concept_name`, `domain_id`, `vocabulary_id`, `concept_class_id`,
  `standard_concept`, `concept_code`, `valid_start_date`, `valid_end_date`, `invalid_reason`
- Standard concepts marked `standard_concept = 'S'`
- Confirmed: SNOMED 38341003 (hypertensive disorder) → concept_id 316866 present

### CONCEPT_RELATIONSHIP.csv (needs Athena download)

Not present locally. Required to translate non-standard source codes via the `Maps to`
relationship. Download from [Athena](https://athena.ohdsi.org) — select vocabularies
SNOMED, ICD10CM, ICD9CM, RxNorm, LOINC at minimum.

## Technology

- **DuckDB** — query CSVs directly without ETL; handles 7M+ rows efficiently
- **Python + FastAPI** — minimal REST layer; one route handler per operation
- **Reference**: `/Users/croeder/git/omop_on_duckdb/` — existing DuckDB + OMOP CSV loading

## Translation logic

For `ConceptMap/$translate` given `(system, code, targetsystem)`:

1. Map FHIR vocabulary URI → OMOP `vocabulary_id`:

| FHIR URI | OMOP vocabulary_id |
|---|---|
| `http://snomed.info/sct` | `SNOMED` |
| `http://hl7.org/fhir/sid/icd-10-cm` | `ICD10CM` |
| `http://hl7.org/fhir/sid/icd-9-cm` | `ICD9CM` |
| `http://www.nlm.nih.gov/research/umls/rxnorm` | `RxNorm` |
| `http://loinc.org` | `LOINC` |

2. Query `CONCEPT` for `concept_code = code` AND `vocabulary_id = <mapped>` AND
   `standard_concept = 'S'` → return `concept_id` directly.

3. If not found as a standard concept, join through `CONCEPT_RELATIONSHIP` on
   `relationship_id = 'Maps to'` to find the standard concept (requires the Athena download).

## Matchbox integration

```yaml
matchbox:
  fhir:
    context:
      txServer: http://localhost:8081/r4
      translateMode: server
```

## Out of scope

- Full OMOP vocabulary coverage beyond what's in the Athena download
- Authentication
- Write operations
