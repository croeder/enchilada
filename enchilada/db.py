import csv
import sqlite3
from pathlib import Path

# OMOP Athena exports are tab-separated with a .csv extension
CSV_DELIMITER = "\t"


def _setup_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS _loaded (
            table_name TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS vocabulary (
            vocabulary_id        TEXT NOT NULL PRIMARY KEY,
            vocabulary_name      TEXT NOT NULL,
            vocabulary_reference TEXT
        );

        CREATE TABLE IF NOT EXISTS concept (
            concept_id    INTEGER NOT NULL,
            concept_code  TEXT    NOT NULL,
            vocabulary_id TEXT    NOT NULL,
            standard_concept TEXT
        );

        CREATE TABLE IF NOT EXISTS concept_relationship (
            concept_id_1    INTEGER NOT NULL,
            concept_id_2    INTEGER NOT NULL,
            relationship_id TEXT    NOT NULL
        );
    """)


def _is_loaded(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM _loaded WHERE table_name = ?", (table_name,)
    ).fetchone()
    return row is not None


def _load_concept(conn: sqlite3.Connection, csv_path: str) -> None:
    print(f"Loading CONCEPT from {csv_path} ...", flush=True)
    conn.execute("PRAGMA synchronous = OFF")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        conn.executemany(
            "INSERT INTO concept VALUES (?, ?, ?, ?)",
            (
                (
                    row["concept_id"],
                    row["concept_code"],
                    row["vocabulary_id"],
                    row["standard_concept"],
                )
                for row in reader
            ),
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_concept ON concept (concept_code, vocabulary_id)"
    )
    conn.execute("INSERT INTO _loaded VALUES ('concept')")
    conn.commit()
    conn.execute("PRAGMA synchronous = NORMAL")
    print("CONCEPT loaded.", flush=True)


def _load_concept_relationship(conn: sqlite3.Connection, csv_path: str) -> None:
    print(f"Loading CONCEPT_RELATIONSHIP from {csv_path} ...", flush=True)
    conn.execute("PRAGMA synchronous = OFF")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        conn.executemany(
            "INSERT INTO concept_relationship VALUES (?, ?, ?)",
            (
                (row["concept_id_1"], row["concept_id_2"], row["relationship_id"])
                for row in reader
            ),
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cr ON concept_relationship (concept_id_1, relationship_id)"
    )
    conn.execute("INSERT INTO _loaded VALUES ('concept_relationship')")
    conn.commit()
    conn.execute("PRAGMA synchronous = NORMAL")
    print("CONCEPT_RELATIONSHIP loaded.", flush=True)


def _load_concept_extra(conn: sqlite3.Connection, csv_path: str) -> None:
    """Load supplemental source concepts (IDs > 2B, standard_concept null).

    Local concept IDs are always > 2B (OMOP rule); Athena concept IDs are always < 2B.
    We clear all > 2B rows before inserting so repeated startups stay idempotent.
    """
    print(f"Loading supplemental concepts from {csv_path} ...", flush=True)
    conn.execute("DELETE FROM concept WHERE concept_id > 2000000000")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        conn.executemany(
            "INSERT INTO concept VALUES (?, ?, ?, ?)",
            (
                (
                    row["concept_id"],
                    row["concept_code"],
                    row["vocabulary_id"],
                    row.get("standard_concept") or None,
                )
                for row in reader
            ),
        )
    conn.commit()
    print("Supplemental concepts loaded.", flush=True)


def _load_concept_relationship_extra(conn: sqlite3.Connection, csv_path: str) -> None:
    """Load supplemental 'Maps to' relationships for local source concepts.

    Local source concept IDs are always > 2B, so we clear those rows before
    inserting to keep repeated startups idempotent.
    """
    print(f"Loading supplemental concept relationships from {csv_path} ...", flush=True)
    conn.execute("DELETE FROM concept_relationship WHERE concept_id_1 > 2000000000")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        conn.executemany(
            "INSERT INTO concept_relationship VALUES (?, ?, ?)",
            (
                (row["concept_id_1"], row["concept_id_2"], row["relationship_id"])
                for row in reader
            ),
        )
    conn.commit()
    print("Supplemental concept relationships loaded.", flush=True)


def _load_vocabulary_extra(conn: sqlite3.Connection, csv_path: str) -> None:
    """Load supplemental vocabulary definitions for locally-added vocabularies."""
    print(f"Loading supplemental vocabularies from {csv_path} ...", flush=True)
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
        conn.executemany(
            "INSERT OR REPLACE INTO vocabulary VALUES (?, ?, ?)",
            (
                (row["vocabulary_id"], row["vocabulary_name"], row.get("vocabulary_reference", ""))
                for row in reader
            ),
        )
    conn.commit()
    print("Supplemental vocabularies loaded.", flush=True)


def init_db(config: dict) -> sqlite3.Connection:
    db_path = config["data"]["sqlite_db"]
    concept_csv = config["data"]["concept_csv"]
    cr_csv = config["data"].get("concept_relationship_csv")
    extra_csv = config["data"].get("concept_extra_csv")
    cr_extra_csv = config["data"].get("concept_relationship_extra_csv")
    vocab_extra_csv = config["data"].get("vocabulary_extra_csv")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA cache_size = -64000")

    _setup_schema(conn)
    conn.commit()

    if not _is_loaded(conn, "concept"):
        _load_concept(conn, concept_csv)

    if cr_csv and not _is_loaded(conn, "concept_relationship"):
        _load_concept_relationship(conn, cr_csv)

    if vocab_extra_csv:
        _load_vocabulary_extra(conn, vocab_extra_csv)

    if extra_csv:
        _load_concept_extra(conn, extra_csv)

    if cr_extra_csv:
        _load_concept_relationship_extra(conn, cr_extra_csv)

    return conn
