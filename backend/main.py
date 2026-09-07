"""
AI FloodShield PAK — FastAPI backend

Endpoints consumed by the Next.js dashboard:
  GET /                 health message
  GET /api/health       dependency checks
  GET /api/status       current fused alert + ML prediction
  GET /api/history      recent Marala observations
  GET /api/model-info   model / project metadata

Set FLOODSHIELD_MODE=local (default) to run against the local CSV + model.
Set FLOODSHIELD_MODE=live to scrape FFD (falls back to local on failure).
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api_service import get_health, get_history, get_model_info, get_status

load_dotenv()

app = FastAPI(
    title="AI FloodShield PAK",
    description="Chenab @ Marala flood-risk API for the FloodShield dashboard.",
    version="1.0.0",
)

_extra_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        *_extra_origins,
    ],
    allow_origin_regex=r"https://.*\.(vercel\.app|netlify\.app|web\.app|firebaseapp\.com|hf\.space)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "AI FloodShield PAK backend is working"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return get_health()


@app.get("/api/status")
def status(
    refresh: bool = Query(
        False,
        description="Bypass the short in-memory status cache",
    ),
) -> dict[str, Any]:
    try:
        return get_status(force_refresh=refresh)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute FloodShield status: {exc}",
        ) from exc


@app.get("/api/history")
def history(
    limit: int = Query(30, ge=1, le=365),
) -> list[dict[str, Any]]:
    try:
        return get_history(limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load history: {exc}",
        ) from exc


@app.get("/api/model-info")
def model_info() -> dict[str, Any]:
    return get_model_info()
