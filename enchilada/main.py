import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .db import init_db
from .translate import translate_r4, translate_r5


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
    description="Local FHIR terminology server backed by OMOP vocabularies. Supports R4 and R5.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Parameter extraction ──────────────────────────────────────────────────────

def _extract_params_r4(body: dict) -> dict[str, str]:
    """Extract R4 ConceptMap/$translate parameters.

    Accepts:
      - system (uri) + code (code) + targetsystem (uri)  [flat]
      - coding (valueCoding {system, code}) + targetsystem (uri)
      - url (uri) used as system fallback when system is absent (FML mapUri convention)
    """
    result = {}
    for param in body.get("parameter", []):
        name = param.get("name")
        if name == "coding" and "valueCoding" in param:
            vc = param["valueCoding"]
            if "system" in vc:
                result["system"] = vc["system"]
            if "code" in vc:
                result["code"] = vc["code"]
            continue
        for key in ("valueUri", "valueCode", "valueString", "valueUrl"):
            if key in param:
                result[name] = param[key]
                break
    # FML bare-code convention: url carries the system URI when system is absent
    if "system" not in result and "url" in result:
        result["system"] = result.pop("url")
    return result


def _extract_params_r5(body: dict) -> dict[str, str]:
    """Extract R5 ConceptMap/$translate parameters.

    Accepts:
      - system (uri) + sourceCode (code) + targetSystem (uri)  [flat]
      - sourceCoding (valueCoding {system, code}) + targetSystem (uri)
      - url (uri) used as system fallback when system is absent (FML mapUri convention)
    """
    result = {}
    for param in body.get("parameter", []):
        name = param.get("name")
        if name == "sourceCoding" and "valueCoding" in param:
            vc = param["valueCoding"]
            if "system" in vc:
                result["system"] = vc["system"]
            if "sourceCode" in vc:
                result["sourceCode"] = vc["sourceCode"]
            elif "code" in vc:
                result["sourceCode"] = vc["code"]
            continue
        for key in ("valueUri", "valueCode", "valueString", "valueUrl"):
            if key in param:
                result[name] = param[key]
                break
    if "system" not in result and "url" in result:
        result["system"] = result.pop("url")
    return result


# ── R4 routes ─────────────────────────────────────────────────────────────────

@app.get("/r4/metadata", summary="CapabilityStatement / TerminologyCapabilities (R4)",
         response_class=JSONResponse)
async def metadata_r4(mode: str | None = None):
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
        "rest": [{"mode": "server", "resource": [{"type": "ConceptMap", "operation": [
            {"name": "translate",
             "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate"}
        ]}]}],
    }


@app.post("/r4/ConceptMap/$translate", summary="ConceptMap/$translate (R4)",
          response_class=JSONResponse)
async def conceptmap_translate_post_r4(request: Request):
    body = await request.json()
    params = _extract_params_r4(body)
    system = params.get("system")
    code = params.get("code")
    targetsystem = params.get("targetsystem", "https://athena.ohdsi.org")
    missing = [n for n, v in [("system", system), ("code", code)] if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameter(s): {', '.join(missing)}")
    return translate_r4(request.app.state.conn, system, code, targetsystem)


@app.get("/r4/ConceptMap/$translate", summary="ConceptMap/$translate GET (R4)",
         response_class=JSONResponse)
async def conceptmap_translate_get_r4(request: Request, system: str, code: str, targetsystem: str):
    return translate_r4(request.app.state.conn, system, code, targetsystem)


# ── R5 routes ─────────────────────────────────────────────────────────────────

@app.get("/r5/metadata", summary="CapabilityStatement / TerminologyCapabilities (R5)",
         response_class=JSONResponse)
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
        "rest": [{"mode": "server", "resource": [{"type": "ConceptMap", "operation": [
            {"name": "translate",
             "definition": "http://hl7.org/fhir/OperationDefinition/ConceptMap-translate"}
        ]}]}],
    }


@app.post("/r5/ConceptMap/$translate", summary="ConceptMap/$translate (R5)",
          response_class=JSONResponse)
async def conceptmap_translate_post_r5(request: Request):
    body = await request.json()
    params = _extract_params_r5(body)
    system = params.get("system")
    sourceCode = params.get("sourceCode")
    targetSystem = params.get("targetSystem", "https://athena.ohdsi.org")
    missing = [n for n, v in [("system", system), ("sourceCode", sourceCode)] if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameter(s): {', '.join(missing)}")
    return translate_r5(request.app.state.conn, system, sourceCode, targetSystem)


@app.get("/r5/ConceptMap/$translate", summary="ConceptMap/$translate GET (R5)",
         response_class=JSONResponse)
async def conceptmap_translate_get_r5(request: Request, system: str, sourceCode: str, targetSystem: str):
    return translate_r5(request.app.state.conn, system, sourceCode, targetSystem)
