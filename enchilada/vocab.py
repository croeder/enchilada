FHIR_URI_TO_VOCAB: dict[str, str] = {
    "http://snomed.info/sct": "SNOMED",
    "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
    "http://hl7.org/fhir/sid/icd-9-cm": "ICD9CM",
    "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
    "http://loinc.org": "LOINC",
}


def fhir_uri_to_vocab_id(uri: str) -> str | None:
    return FHIR_URI_TO_VOCAB.get(uri)
