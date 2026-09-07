"""Hugging Face Spaces entrypoint (Gradio SDK).

Free Spaces cannot use Docker here, so this file wraps the existing FastAPI
app in Gradio and still exposes the dashboard REST routes:

  GET /api/health
  GET /api/status
  GET /api/history
  GET /api/model-info
  GET /docs
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

try:
    import spaces
except ImportError:  # CPU Spaces do not ship this package

    class spaces:  # type: ignore[no-redef]
        @staticmethod
        def GPU(fn=None, **_kwargs):
            def deco(func):
                return func

            return deco if fn is None else deco(fn)


@spaces.GPU
def _zero_gpu_placeholder() -> str:
    """ZeroGPU Spaces refuse to boot unless at least one @spaces.GPU exists.

    The flood model is sklearn on CPU; this function is never called.
    """
    return "ok"


import gradio as gr
from api_service import get_health, get_status
from main import app as backend_app


def _health_payload() -> dict:
    try:
        return get_health()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _status_payload() -> dict:
    try:
        return get_status(force_refresh=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


with gr.Blocks(title="AI FloodShield PAK") as demo:
    gr.Markdown(
        """
# AI FloodShield PAK
Chenab River @ Marala — flood-risk API for the dashboard.

**REST endpoints** (use these from the Next.js app):
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
    health_btn.click(_health_payload, outputs=output)
    status_btn.click(_status_payload, outputs=output)

app = gr.mount_gradio_app(backend_app, demo, path="/ui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860"))),
    )
