import sqlite3
from .vocab import fhir_uri_to_vocab_id


def translate(conn: sqlite3.Connection, system: str, code: str, targetsystem: str) -> dict:
    vocab_id = fhir_uri_to_vocab_id(system)
    if vocab_id is None:
        return _no_match(system, code, f"Unknown vocabulary system: {system}")

    # Step 1: direct standard concept lookup
    row = conn.execute(
        """
        SELECT concept_id FROM concept
        WHERE concept_code = ? AND vocabulary_id = ? AND standard_concept = 'S'
        """,
        (code, vocab_id),
    ).fetchone()

    if row:
        return _match(targetsystem, str(row["concept_id"]))

    # Step 2: non-standard code mapped via 'Maps to' relationship.
    # The relationship itself is authoritative; we don't require the target to exist
    # in the local concept table (supplemental concept_ids from Athena may not be present).
    row = conn.execute(
        """
        SELECT cr.concept_id_2 AS concept_id
        FROM concept c1
        JOIN concept_relationship cr ON cr.concept_id_1 = c1.concept_id
                                     AND cr.relationship_id = 'Maps to'
        WHERE c1.concept_code = ? AND c1.vocabulary_id = ?
        LIMIT 1
        """,
        (code, vocab_id),
    ).fetchone()

    if row:
        return _match(targetsystem, str(row["concept_id"]))

    return _no_match(system, code)


def _match(targetsystem: str, concept_id: str) -> dict:
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": True},
            {
                "name": "match",
                "part": [
                    {"name": "equivalence", "valueCode": "equivalent"},
                    {
                        "name": "concept",
                        "valueCoding": {"system": targetsystem, "code": concept_id},
                    },
                ],
            },
        ],
    }


def _no_match(system: str, code: str, reason: str | None = None) -> dict:
    vocab_id = fhir_uri_to_vocab_id(system) or system
    message = reason or f"No mapping found for {vocab_id}#{code}"
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": False},
            {"name": "message", "valueString": message},
        ],
    }
