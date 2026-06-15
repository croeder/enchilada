import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .db import init_db
from .translate import translate as do_translate


def _load_config() -> dict:
    path = os.environ.get("ENCHILADA_CONFIG", "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = _load_config()
    app.state.conn = init_db(config)
    yield
    app.state.conn.close()


app = FastAPI(
    title="enchilada",
    description="Local FHIR R4 terminology server backed by OMOP vocabularies.",
    version="0.1.0",
    lifespan=lifespan,
)


def _extract_params(body: dict) -> dict[str, str]:
    """Pull named values out of a FHIR Parameters resource."""
    result = {}
    for param in body.get("parameter", []):
        name = param.get("name")
        for key in ("valueUri", "valueCode", "valueString", "valueUrl"):
            if key in param:
                result[name] = param[key]
                break
    return result


@app.get(
    "/r4/metadata",
    summary="CapabilityStatement / TerminologyCapabilities",
    description=(
        "Returns a CapabilityStatement normally, "
        "or a TerminologyCapabilities when ?mode=terminology."
    ),
    response_class=JSONResponse,
)
async def metadata(mode: str | None = None):
    if mode == "terminology":
        return {
            "resourceType": "TerminologyCapabilities",
            "status": "active",
            "date": "2025-05-22",
            "kind": "instance",
            "codeSystem": [
                {"uri": "http://snomed.info/sct"},
                {"uri": "http://hl7.org/fhir/sid/icd-10-cm"},
                {"uri": "http://hl7.org/fhir/sid/icd-9-cm"},
                {"uri": "http://www.nlm.nih.gov/research/umls/rxnorm"},
                {"uri": "http://loinc.org"},
            ],
            "translation": {"needsMap": False},
        }
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2025-05-22",
        "kind": "instance",
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json", "application/json"],
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "ConceptMap",
                        "operation": [
                            {
                                "name": "translate",
                                "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate",
                            }
                        ],
                    }
                ],
            }
        ],
    }


@app.post(
    "/r4/ConceptMap/$translate",
    summary="ConceptMap/$translate",
    description=(
        "Translate a source code to an OMOP concept ID. "
        "Accepts a FHIR R4 Parameters resource; returns a Parameters resource."
    ),
    response_class=JSONResponse,
)
async def conceptmap_translate_post(request: Request):
    body = await request.json()
    import logging; logging.getLogger("enchilada").warning("translate body: %s", body)
    params = _extract_params(body)

    system = params.get("system")
    code = params.get("code")
    targetsystem = params.get("targetsystem", "https://athena.ohdsi.org")
    url = params.get("url")

    # Bare FHIR code types (e.g. Patient.gender) carry no system URI.
    # FML maps pass the implicit system URI as the translate() mapUri, which
    # arrives here as the 'url' parameter.  Fall back to it when 'system' is absent.
    if not system and url:
        system = url

    missing = [n for n, v in [("system", system), ("code", code)] if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameter(s): {', '.join(missing)}")

    return do_translate(request.app.state.conn, system, code, targetsystem)


@app.get(
    "/r4/ConceptMap/$translate",
    summary="ConceptMap/$translate (GET)",
    description="Convenience GET form — accepts system, code, targetsystem as query parameters.",
    response_class=JSONResponse,
)
async def conceptmap_translate_get(request: Request, system: str, code: str, targetsystem: str):
    return do_translate(request.app.state.conn, system, code, targetsystem)


# ---------------------------------------------------------------------------
# R5 routes — same translate logic, /r5/ prefix, fhirVersion 5.0.0
# ---------------------------------------------------------------------------

@app.get("/r5/metadata", summary="CapabilityStatement / TerminologyCapabilities (R5)", response_class=JSONResponse)
async def metadata_r5(mode: str | None = None):
    if mode == "terminology":
        return {
            "resourceType": "TerminologyCapabilities",
            "status": "active",
            "date": "2025-05-22",
            "kind": "instance",
            "codeSystem": [
                {"uri": "http://snomed.info/sct"},
                {"uri": "http://hl7.org/fhir/sid/icd-10-cm"},
                {"uri": "http://hl7.org/fhir/sid/icd-9-cm"},
                {"uri": "http://www.nlm.nih.gov/research/umls/rxnorm"},
                {"uri": "http://loinc.org"},
            ],
            "translation": {"needsMap": False},
        }
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2025-05-22",
        "kind": "instance",
        "fhirVersion": "5.0.0",
        "format": ["application/fhir+json", "application/json"],
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "ConceptMap",
                        "operation": [
                            {
                                "name": "translate",
                                "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate",
                            }
                        ],
                    }
                ],
            }
        ],
    }


@app.post("/r5/ConceptMap/$translate", summary="ConceptMap/$translate (R5)", response_class=JSONResponse)
async def conceptmap_translate_post_r5(request: Request):
    body = await request.json()
    params = _extract_params(body)
    system = params.get("system")
    code = params.get("code")
    targetsystem = params.get("targetsystem", "https://athena.ohdsi.org")
    url = params.get("url")
    if not system and url:
        system = url
    missing = [n for n, v in [("system", system), ("code", code)] if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameter(s): {', '.join(missing)}")
    return do_translate(request.app.state.conn, system, code, targetsystem)


@app.get("/r5/ConceptMap/$translate", summary="ConceptMap/$translate (R5 GET)", response_class=JSONResponse)
async def conceptmap_translate_get_r5(request: Request, system: str, code: str, targetsystem: str):
    return do_translate(request.app.state.conn, system, code, targetsystem)
