from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import load_environment
from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeleteProfileResponse,
    SavedProfile,
    SavedProfileSummary,
)
from backend.pipeline import analyze_neighborhood
from backend.storage import (
    delete_saved_profile,
    get_saved_profile,
    initialize_database,
    list_saved_profiles,
    save_profile,
)

load_environment()

try:
    initialize_database()
except Exception:
    pass

app = FastAPI(title="VibeCheck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return await analyze_neighborhood(request)


@app.post("/profiles", response_model=SavedProfile)
async def create_profile(response: AnalyzeResponse) -> SavedProfile:
    return save_profile(response)


@app.get("/profiles", response_model=list[SavedProfileSummary])
async def profiles() -> list[SavedProfileSummary]:
    return list_saved_profiles()


@app.get("/profiles/{profile_id}", response_model=SavedProfile)
async def profile(profile_id: str) -> SavedProfile:
    saved = get_saved_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return saved


@app.delete("/profiles/{profile_id}", response_model=DeleteProfileResponse)
async def delete_profile(profile_id: str) -> DeleteProfileResponse:
    deleted = delete_saved_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return DeleteProfileResponse(deleted=True)
