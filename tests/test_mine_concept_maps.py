"""Tests for matchbox_scripts/mine_concept_maps.py."""

import json
import sys
from pathlib import Path

import pytest

# mine_concept_maps.py lives in matchbox_scripts, not in the enchilada package.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "matchbox_scripts"))
from mine_concept_maps import local_concept_id, mine_concept_maps  # noqa: E402


# ---------------------------------------------------------------------------
# local_concept_id tests
# ---------------------------------------------------------------------------

class TestLocalConceptId:
    def test_WHEN_any_vocab_and_code_SHOULD_return_gt_2billion(self):
        assert local_concept_id("AdministrativeGender", "male") > 2_000_000_000

    def test_WHEN_any_vocab_and_code_SHOULD_return_lt_3billion(self):
        assert local_concept_id("AdministrativeGender", "male") < 3_000_000_000

    def test_WHEN_same_inputs_SHOULD_return_same_id(self):
        id1 = local_concept_id("AdministrativeGender", "male")
        id2 = local_concept_id("AdministrativeGender", "male")
        assert id1 == id2

    def test_WHEN_different_codes_SHOULD_return_different_ids(self):
        assert local_concept_id("AdministrativeGender", "male") != \
               local_concept_id("AdministrativeGender", "female")

    def test_WHEN_different_vocab_same_code_SHOULD_return_different_ids(self):
        assert local_concept_id("AdministrativeGender", "food") != \
               local_concept_id("AllergyIntoleranceCategory", "food")

    def test_WHEN_all_gender_codes_SHOULD_be_unique(self):
        codes = ["male", "female", "other", "unknown"]
        ids = [local_concept_id("AdministrativeGender", c) for c in codes]
        assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# mine_concept_maps tests using synthetic IG output
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_ig(tmp_path) -> Path:
    """Write a minimal ConceptMap JSON mimicking the IG output."""
    cm = {
        "resourceType": "ConceptMap",
        "id": "GenderClass",
        "group": [
            {
                "source": "http://hl7.org/fhir/administrative-gender",
                "target": "https://fhir-terminology.ohdsi.org",
                "element": [
                    {"code": "male",    "target": [{"code": "8507",  "relationship": "equivalent"}]},
                    {"code": "female",  "target": [{"code": "8532",  "relationship": "equivalent"}]},
                    {"code": "other",   "target": [{"code": "44814653", "relationship": "equivalent"}]},
                    {"code": "unknown", "target": [{"code": "8551",  "relationship": "equivalent"}]},
                ],
            }
        ],
    }
    (tmp_path / "ConceptMap-GenderClass.json").write_text(json.dumps(cm))
    return tmp_path


@pytest.fixture
def synthetic_ig_with_snomed(tmp_path) -> Path:
    """ConceptMap for a standard SNOMED vocabulary (backfill path)."""
    cm = {
        "resourceType": "ConceptMap",
        "id": "ClinicalFindings",
        "group": [
            {
                "source": "http://snomed.info/sct",
                "target": "https://fhir-terminology.ohdsi.org",
                "element": [
                    {"code": "386661006", "target": [{"code": "437663", "relationship": "equivalent"}]},
                ],
            }
        ],
    }
    (tmp_path / "ConceptMap-ClinicalFindings.json").write_text(json.dumps(cm))
    return tmp_path


class TestMineConceptMaps:
    def test_WHEN_local_vocab_SHOULD_generate_concept_with_id_gt_2billion(self, synthetic_ig):
        concepts, _, _ = mine_concept_maps(synthetic_ig)
        gender_concepts = [c for c in concepts if c["vocabulary_id"] == "AdministrativeGender"]
        assert len(gender_concepts) == 4
        for row in gender_concepts:
            assert int(row["concept_id"]) > 2_000_000_000

    def test_WHEN_local_vocab_SHOULD_set_empty_standard_concept(self, synthetic_ig):
        concepts, _, _ = mine_concept_maps(synthetic_ig)
        for row in [c for c in concepts if c["vocabulary_id"] == "AdministrativeGender"]:
            assert row["standard_concept"] == ""

    def test_WHEN_local_vocab_SHOULD_generate_maps_to_relationships(self, synthetic_ig):
        concepts, relationships, _ = mine_concept_maps(synthetic_ig)
        male_concept_id = next(
            c["concept_id"] for c in concepts
            if c["vocabulary_id"] == "AdministrativeGender" and c["concept_code"] == "male"
        )
        rel = next(
            (r for r in relationships if r["concept_id_1"] == male_concept_id), None
        )
        assert rel is not None
        assert rel["concept_id_2"] == "8507"
        assert rel["relationship_id"] == "Maps to"

    def test_WHEN_local_vocab_SHOULD_generate_vocabulary_entry(self, synthetic_ig):
        _, _, vocab_ids = mine_concept_maps(synthetic_ig)
        assert "AdministrativeGender" in vocab_ids

    def test_WHEN_standard_system_SHOULD_generate_backfill_concept_with_athena_id(
        self, synthetic_ig_with_snomed
    ):
        concepts, relationships, _ = mine_concept_maps(synthetic_ig_with_snomed)
        snomed_rows = [c for c in concepts if c["vocabulary_id"] == "SNOMED"]
        assert len(snomed_rows) == 1
        assert snomed_rows[0]["concept_id"] == "437663"
        assert snomed_rows[0]["standard_concept"] == "S"

    def test_WHEN_standard_system_SHOULD_not_generate_relationship_rows(
        self, synthetic_ig_with_snomed
    ):
        _, relationships, _ = mine_concept_maps(synthetic_ig_with_snomed)
        assert len(relationships) == 0

    def test_WHEN_standard_system_SHOULD_not_generate_vocabulary_entry(
        self, synthetic_ig_with_snomed
    ):
        _, _, vocab_ids = mine_concept_maps(synthetic_ig_with_snomed)
        assert "SNOMED" not in vocab_ids

    def test_WHEN_unknown_source_system_SHOULD_skip_and_warn(self, tmp_path, capsys):
        cm = {
            "resourceType": "ConceptMap",
            "id": "Unknown",
            "group": [{"source": "http://example.com/unknown", "element": []}],
        }
        (tmp_path / "ConceptMap-Unknown.json").write_text(json.dumps(cm))
        mine_concept_maps(tmp_path)
        err = capsys.readouterr().err
        assert "unknown source system" in err
