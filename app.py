"""Hugging Face Spaces entrypoint (Gradio + ZeroGPU).

ZeroGPU must call Gradio's own launch(). Dashboard REST routes are attached
to that same FastAPI app so /api/* and the Gradio UI share one port.

  GET /api/health
  GET /api/status
  GET /api/history
  GET /api/model-info
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(ROOT / ".env")

import spaces
import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from gradio.routes import App

from api_service import get_health, get_status
from main import app as backend_app

_ORIG_CREATE_APP = App.create_app


@classmethod  # type: ignore[misc]
def _create_app_with_api(cls, *args, **kwargs):
    fastapi_app = _ORIG_CREATE_APP(*args, **kwargs)
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_origin_regex=(
            r"https://.*\.(vercel\.app|netlify\.app|web\.app|"
            r"firebaseapp\.com|hf\.space)"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for route in backend_app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api"):
            fastapi_app.routes.append(route)
    return fastapi_app


App.create_app = _create_app_with_api


@spaces.GPU
def gpu_health() -> dict:
    try:
        return get_health()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


@spaces.GPU
def gpu_status() -> dict:
    try:
        return get_status(force_refresh=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


with gr.Blocks(title="AI FloodShield PAK") as demo:
    gr.Markdown(
        """
# AI FloodShield PAK
Chenab River @ Marala — flood-risk API for the dashboard.

**REST endpoints** (used by the Next.js app):
- `/api/health`
- `/api/status`
- `/api/history`
- `/api/model-info`
        """
    )
    with gr.Row():
        health_btn = gr.Button("Health check")
        status_btn = gr.Button("Current flood status")
    output = gr.JSON(label="Response")
    health_btn.click(fn=gpu_health, outputs=output)
    status_btn.click(fn=gpu_status, outputs=output)

demo.queue()
demo.launch(server_name="0.0.0.0", server_port=7860)
