from fastapi import FastAPI

from backend.models import AnalyzeRequest, AnalyzeResponse
from backend.pipeline import analyze_neighborhood

app = FastAPI(title="VibeCheck API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    return await analyze_neighborhood(request)
