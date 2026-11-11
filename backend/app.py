import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from database import add_claim, clear_claims, get_claims
from extractor import extract_text_from_pdf, extract_text_from_txt, extract_fields
from llm_extractor import (
    extract_fields_with_gemini,
    get_gemini_status,
    route_claim_with_gemini,
)
from validator import find_missing_fields
from router import route_claim

app = FastAPI(title="Claims Operations Workbench")
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/process-fnol")
async def process_fnol(file: UploadFile = File(...)):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    original_filename = Path(file.filename or "fnol-document").name
    file_extension = Path(original_filename).suffix.lower()

    if file_extension not in [".pdf", ".txt"]:
        return {"error": "Only PDF and TXT files are supported"}

    stored_filename = f"{uuid4().hex}_{original_filename}"
    file_path = UPLOAD_DIR / stored_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if file_extension == ".pdf":
        text = extract_text_from_pdf(file_path)
    else:
        text = extract_text_from_txt(file_path)

    regex_fields = extract_fields(text)
    fields, llm_status = extract_fields_with_gemini(text, regex_fields)
    missing_fields = find_missing_fields(fields)
    rule_routing_result = route_claim(fields, missing_fields)
    routing_result, llm_routing_status = route_claim_with_gemini(
        text,
        fields,
        missing_fields,
        rule_routing_result,
    )

    claim = add_claim({
        "fileName": original_filename,
        "storedFileName": stored_filename,
        "storedFilePath": str(file_path.relative_to(BASE_DIR)),
        "extractedFields": fields,
        "missingFields": missing_fields,
        "recommendedRoute": routing_result["route"],
        "reasoning": routing_result["reasoning"],
        "extractionMethod": llm_status["method"],
        "llmStatus": llm_status,
        "routingMethod": llm_routing_status["method"],
        "llmRoutingStatus": llm_routing_status,
    })

    return claim


@app.get("/llm-status")
async def llm_status():
    return get_gemini_status()


@app.get("/claims")
async def list_claims():
    return get_claims()


@app.delete("/claims")
async def delete_claims():
    clear_claims()
    return {"message": "Claim history cleared", "claims": []}

# Human-in-the-loop workbench; legacy FNOL endpoints remain available.
from workbench import router as workbench_router
app.include_router(workbench_router)

from evaluation import router as evaluation_router
app.include_router(evaluation_router)
