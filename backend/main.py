from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import load_environment
from backend.doctor import collect_health
from backend.models import (
    AnalysisLensMode,
    AnalysisLensSnapshot,
    AnalyzeRequest,
    AnalyzeResponse,
    DeletePreferenceProfileResponse,
    DeleteProfileResponse,
    PreferenceProfile,
    PreferenceProfileCreate,
    PreferenceProfileUpdate,
    SaveProfileRequest,
    SavedProfile,
    SavedProfileSummary,
)
from backend.pipeline import analyze_neighborhood
from backend.storage import (
    build_refresh_request,
    create_preference_profile,
    delete_preference_profile,
    delete_saved_profile,
    get_preference_profile,
    get_saved_profile,
    initialize_database,
    list_preference_profiles,
    list_saved_profiles,
    save_profile,
    set_default_preference_profile,
    update_preference_profile,
    update_saved_profile,
)

load_environment()

try:
    initialize_database()
except Exception:
    pass

app = FastAPI(title="VibeCheck API")

LOCAL_VITE_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1):517[0-9]$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=LOCAL_VITE_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    return collect_health()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    lens = AnalysisLensSnapshot(
        mode=AnalysisLensMode.GENERIC
        if request.generic_mode
        else AnalysisLensMode.CUSTOM,
        profile_name="Generic" if request.generic_mode else "Custom preferences",
        preferences=request.preferences,
    )
    if request.preference_profile_id is not None:
        profile = get_preference_profile(request.preference_profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Preference profile not found.")
        request = request.model_copy(
            update={
                "preferences": profile.preferences,
                "generic_mode": profile.generic_mode,
            }
        )
        lens = AnalysisLensSnapshot(
            mode=AnalysisLensMode.GENERIC
            if profile.generic_mode
            else AnalysisLensMode.SAVED_PROFILE,
            profile_id=profile.id,
            profile_name=profile.name,
            preferences=profile.preferences,
        )
    return await analyze_neighborhood(request, analysis_lens=lens)


@app.post("/preference-profiles", response_model=PreferenceProfile)
async def create_preference_profile_endpoint(
    profile: PreferenceProfileCreate,
) -> PreferenceProfile:
    return create_preference_profile(profile)


@app.get("/preference-profiles", response_model=list[PreferenceProfile])
async def preference_profiles() -> list[PreferenceProfile]:
    return list_preference_profiles()


@app.get("/preference-profiles/{profile_id}", response_model=PreferenceProfile)
async def preference_profile(profile_id: str) -> PreferenceProfile:
    profile = get_preference_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile


@app.put("/preference-profiles/{profile_id}", response_model=PreferenceProfile)
async def update_preference_profile_endpoint(
    profile_id: str,
    update: PreferenceProfileUpdate,
) -> PreferenceProfile:
    profile = update_preference_profile(profile_id, update)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile


@app.delete(
    "/preference-profiles/{profile_id}", response_model=DeletePreferenceProfileResponse
)
async def delete_preference_profile_endpoint(
    profile_id: str,
) -> DeletePreferenceProfileResponse:
    deleted = delete_preference_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return DeletePreferenceProfileResponse(deleted=True)


@app.post("/preference-profiles/{profile_id}/default", response_model=PreferenceProfile)
async def default_preference_profile(profile_id: str) -> PreferenceProfile:
    profile = set_default_preference_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preference profile not found.")
    return profile


@app.post("/profiles", response_model=SavedProfile)
async def create_profile(payload: SaveProfileRequest | AnalyzeResponse) -> SavedProfile:
    if isinstance(payload, AnalyzeResponse):
        return save_profile(payload)
    return save_profile(payload.response, analyze_request=payload.analyze_request)


@app.get("/profiles", response_model=list[SavedProfileSummary])
async def profiles() -> list[SavedProfileSummary]:
    return list_saved_profiles()


@app.post("/profiles/{profile_id}/refresh", response_model=SavedProfile)
async def refresh_profile(profile_id: str) -> SavedProfile:
    saved = get_saved_profile(profile_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")

    request = build_refresh_request(saved)
    lens = saved.analysis_lens
    request = request.model_copy(
        update={
            "preference_profile_id": None,
            "preferences": lens.preferences,
            "generic_mode": lens.mode
            in {AnalysisLensMode.GENERIC, AnalysisLensMode.LEGACY},
        }
    )
    response = await analyze_neighborhood(request, analysis_lens=lens)
    updated = update_saved_profile(profile_id, response, analyze_request=request)
    if updated is None:
        raise HTTPException(status_code=404, detail="Saved profile not found.")
    return updated


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
