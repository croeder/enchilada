# API Reference

enchilada exposes a minimal FHIR R4 terminology server API. An interactive
Swagger UI is available at `/docs` when the server is running.

## `GET /r4/metadata`

Returns a capability statement describing the server.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `mode` | query string | `terminology` — returns a `TerminologyCapabilities` resource instead of a `CapabilityStatement` |

**Response (default)**

```json
{
  "resourceType": "CapabilityStatement",
  "status": "active",
  "fhirVersion": "4.0.1",
  "format": ["application/fhir+json", "application/json"],
  "rest": [{ "mode": "server", ... }]
}
```

**Response (`?mode=terminology`)**

```json
{
  "resourceType": "TerminologyCapabilities",
  "codeSystem": [
    { "uri": "http://snomed.info/sct" },
    { "uri": "http://loinc.org" },
    ...
  ]
}
```

---

## `POST /r4/ConceptMap/$translate`

Translate a source code to an OMOP concept ID.

**Request body** — FHIR R4 `Parameters` resource

```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "system",       "valueUri":  "http://snomed.info/sct" },
    { "name": "code",         "valueCode": "38341003" },
    { "name": "targetsystem", "valueUri":  "https://athena.ohdsi.org" }
  ]
}
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `system` | Yes* | Source code system URI. See note below on bare codes. |
| `code` | Yes | Source code value. |
| `url` | No | ConceptMap URL (or system URI — see [Bare FHIR code types](fhir-conventions.md#bare-fhir-code-types)). |
| `targetsystem` | No | Target system. Defaults to `https://athena.ohdsi.org`. |

*`system` may be omitted when `url` contains a known FHIR vocabulary system URI.
See [bare code convention](fhir-conventions.md#bare-fhir-code-types).

**Response — match found**

```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "result", "valueBoolean": true },
    {
      "name": "match",
      "part": [
        { "name": "equivalence", "valueCode": "equivalent" },
        { "name": "concept", "valueCoding": { "system": "https://athena.ohdsi.org", "code": "316866" } }
      ]
    }
  ]
}
```

**Response — no match**

```json
{
  "resourceType": "Parameters",
  "parameter": [
    { "name": "result",  "valueBoolean": false },
    { "name": "message", "valueString":  "No mapping found for SNOMED#999999" }
  ]
}
```

**Error responses**

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | `code` is missing, or both `system` and `url` are absent |

---

## `GET /r4/ConceptMap/$translate`

Convenience GET form of the translate operation.

**Query parameters:** `system`, `code`, `targetsystem` (same as POST body parameters).

**Example**

```
GET /r4/ConceptMap/$translate?system=http://snomed.info/sct&code=38341003&targetsystem=https://athena.ohdsi.org
```

---

## Lookup algorithm

1. **Step 1 — standard concept**: look up `(concept_code, vocabulary_id)` with
   `standard_concept = 'S'` in the concept table. Return the concept ID if found.

2. **Step 2 — non-standard via `Maps to`**: look up the concept, then follow a
   `Maps to` relationship to a standard concept. Used for supplemental FHIR
   administrative codes (gender, allergy category, etc.).

3. **No match**: return `result = false` with a message.

The FHIR system URI is mapped to an OMOP `vocabulary_id` via the table in
`enchilada/vocab.py`.
