FHIR_URI_TO_VOCAB: dict[str, str] = {
    # Standard clinical terminologies (codes are in CONCEPT.csv)
    "http://snomed.info/sct": "SNOMED",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
    "http://hl7.org/fhir/sid/icd-9-cm": "ICD9CM",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://loinc.org": "LOINC",
    # FHIR administrative code systems (entries loaded from concept_extra.tsv)
    "http://hl7.org/fhir/administrative-gender": "AdministrativeGender",
    "http://hl7.org/fhir/allergy-intolerance-category": "AllergyIntoleranceCategory",
    "http://hl7.org/fhir/intolerance-category": "IntoleranceCategory",
    "http://hl7.org/fhir/sid/cvx": "CVX",
    "http://terminology.hl7.org/CodeSystem/v3-ActCode": "v3-ActCode",
    "http://terminology.hl7.org/CodeSystem/admit-source": "AdmitSource",
    "http://terminology.hl7.org/CodeSystem/discharge-disposition": "DischargeDisposition",
    "http://terminology.hl7.org/CodeSystem/v3-RouteOfAdministration": "RouteOfAdministration",
    "http://terminology.hl7.org/CodeSystem/immunization-origin": "ImmunizationOrigin",
    "http://terminology.hl7.org/CodeSystem/condition-clinical": "ConditionClinical",
}


def fhir_uri_to_vocab_id(uri: str) -> str | None:
    return FHIR_URI_TO_VOCAB.get(uri)
