from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import load_environment
from backend.models import AnalyzeRequest, AnalyzeResponse
from backend.pipeline import analyze_neighborhood

load_environment()

app = FastAPI(title="VibeCheck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return await analyze_neighborhood(request)
