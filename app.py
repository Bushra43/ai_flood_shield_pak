"""Hugging Face Spaces entrypoint (Gradio + ZeroGPU).

Keeps the FastAPI dashboard routes:

  GET /api/health
  GET /api/status
  GET /api/history
  GET /api/model-info
  GET /docs

ZeroGPU requires @spaces.GPU on functions that Gradio actually calls.
"""

from __future__ import annotations

import os
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
from api_service import get_health, get_status
from main import app as backend_app


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
- `/docs`
        """
    )
    with gr.Row():
        health_btn = gr.Button("Health check")
        status_btn = gr.Button("Current flood status")
    output = gr.JSON(label="Response")
    health_btn.click(fn=gpu_health, outputs=output)
    status_btn.click(fn=gpu_status, outputs=output)

demo.queue()
app = gr.mount_gradio_app(backend_app, demo, path="/ui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860"))),
    )
