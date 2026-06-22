import sqlite3
from .vocab import fhir_uri_to_vocab_id


def _lookup(conn: sqlite3.Connection, system: str, code: str) -> str | None:
    """Return the OMOP concept_id string for (system, code), or None if not found."""
    vocab_id = fhir_uri_to_vocab_id(system)
    if vocab_id is None:
        return None

    row = conn.execute(
        """
        SELECT concept_id FROM concept
        WHERE concept_code = ? AND vocabulary_id = ? AND standard_concept = 'S'
        """,
        (code, vocab_id),
    ).fetchone()
    if row:
        return str(row["concept_id"])

    # Step 2: non-standard code mapped via 'Maps to' relationship.
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
        return str(row["concept_id"])

    return None


def _lookup_by_code(conn: sqlite3.Connection, code: str) -> str | None:
    """Return OMOP concept_id by code alone, searching across all standard concepts.

    Used when matchbox omits the system URI from the $translate request body — a known
    matchbox behaviour when translate() is called in FML with an empty ConceptMap URL
    (e.g. translate(coding, '', 'code')). The system is stripped from the Coding before
    the HTTP call is made, so only the code arrives. Ambiguous if the same code exists in
    multiple vocabularies; in practice the OMOP Athena vocabulary set has very little
    cross-vocabulary code collision for clinical codes.
    """
    row = conn.execute(
        """
        SELECT concept_id FROM concept
        WHERE concept_code = ? AND standard_concept = 'S'
        LIMIT 1
        """,
        (code,),
    ).fetchone()
    return str(row["concept_id"]) if row else None


# ── R4 ───────────────────────────────────────────────────────────────────────

def translate_r4(conn: sqlite3.Connection, system: str | None, code: str, targetsystem: str) -> dict:
    if not system:
        concept_id = _lookup_by_code(conn, code)
        if concept_id:
            return _match_r4(targetsystem, concept_id)
        return _no_match_r4(None, code, f"No standard concept found for code {code} (system not provided)")
    if fhir_uri_to_vocab_id(system) is None:
        return _no_match_r4(system, code, f"Unknown vocabulary system: {system}")
    concept_id = _lookup(conn, system, code)
    if concept_id:
        return _match_r4(targetsystem, concept_id)
    return _no_match_r4(system, code)


def _match_r4(targetsystem: str, concept_id: str) -> dict:
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": True},
            {
                "name": "match",
                "part": [
                    {"name": "equivalence", "valueCode": "equivalent"},
                    {"name": "concept", "valueCoding": {"system": targetsystem, "code": concept_id}},
                ],
            },
        ],
    }


def _no_match_r4(system: str | None, code: str, reason: str | None = None) -> dict:
    vocab_id = (fhir_uri_to_vocab_id(system) or system) if system else "(no system)"
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": False},
            {"name": "message", "valueString": reason or f"No mapping found for {vocab_id}#{code}"},
        ],
    }


# ── R5 ───────────────────────────────────────────────────────────────────────

def translate_r5(conn: sqlite3.Connection, system: str | None, code: str, targetSystem: str) -> dict:
    if not system:
        concept_id = _lookup_by_code(conn, code)
        if concept_id:
            return _match_r5(targetSystem, concept_id)
        return _no_match_r5(None, code, f"No standard concept found for code {code} (system not provided)")
    if fhir_uri_to_vocab_id(system) is None:
        return _no_match_r5(system, code, f"Unknown vocabulary system: {system}")
    concept_id = _lookup(conn, system, code)
    if concept_id:
        return _match_r5(targetSystem, concept_id)
    return _no_match_r5(system, code)


def _match_r5(targetSystem: str, concept_id: str) -> dict:
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": True},
            {
                "name": "match",
                "part": [
                    {"name": "relationship", "valueCode": "equivalent"},
                    {"name": "concept", "valueCoding": {"system": targetSystem, "code": concept_id}},
                ],
            },
        ],
    }


def _no_match_r5(system: str | None, code: str, reason: str | None = None) -> dict:
    vocab_id = (fhir_uri_to_vocab_id(system) or system) if system else "(no system)"
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "result", "valueBoolean": False},
            {"name": "message", "valueString": reason or f"No mapping found for {vocab_id}#{code}"},
        ],
    }
