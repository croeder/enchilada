# enchilada

**enchilada** is a local FHIR R4 terminology server that translates FHIR codes to
[OMOP](https://ohdsi.github.io/CommonDataModel/) concept IDs. It is designed to run
alongside [matchbox](https://github.com/ahdis/matchbox) as the `txServer` for
FHIR Mapping Language (FML) `translate()` calls during FHIR-to-OMOP ETL.

## Architecture

```
FHIR Patient/Observation/...
        │
        ▼
   matchbox ($transform)
        │  FML translate()
        ▼
   enchilada (/r4/ConceptMap/$translate)
        │
        ▼
   OMOP concept_id
```

enchilada is backed by:

- **CONCEPT.csv** from an [Athena](https://athena.ohdsi.org) vocabulary download
  (SNOMED, LOINC, RxNorm, ICD-10-CM, …)
- **Supplemental TSV files** for FHIR administrative code systems
  (AdministrativeGender, AllergyIntoleranceCategory, v3-ActCode, CVX, …)

## Quick start

```bash
pip install -e .
# edit config.yaml to point at your CONCEPT.csv and SQLite path
python -m enchilada
```

See [Configuration](configuration.md) for the full config file reference.

## Supported FHIR version

enchilada supports **R4 only**. R5 requests are not handled.
