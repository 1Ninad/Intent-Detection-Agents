""" FastAPI app exposing /run. Orchestrator entrypoint.
Accepts freeText from Streamlit and passes it into the pipeline state. """

from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.classifier.classifier_types import RunRequest
from services.orchestrator.flow import run_pipeline
from services.orchestrator.db import postgres_client
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Intent Orchestrator", version="1.0.0")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize PostgreSQL database schema"""
    postgres_client.init_database()

# Configure CORS to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local Next.js frontend
        "http://localhost:8501",  # Local Streamlit frontend
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
        "https://intent-frontend-584414482857.asia-south1.run.app",  # Production frontend

        "https://salesfinder.vercel.app",
        "*",  # Allow all origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/run")
async def run_endpoint(request: RunRequest):
    """
    Step 2 hand-off:
    - FastAPI parses body into RunRequest (freeText/useWebSearch supported).
    - Pass the request object to run_pipeline, which will propagate fields
      into the orchestrator state (flow.py).
    """
    out = run_pipeline(request)

    return {
        "runId": f"run_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "processedCompanies": out["processedCompanies"],
        "labeledSignals": out["labeledSignals"],
        "results": out["results"],
        "echo": {
            "configId": request.configId,
            "topK": request.topK,
            "useWebSearch": request.useWebSearch,
            "hasFreeText": bool((request.freeText or "").strip()),
        },
    }