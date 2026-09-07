"""Hugging Face Spaces entrypoint (Gradio + ZeroGPU).

ZeroGPU owns Gradio launch() on port 7860. Dashboard REST routes are added
as HTTP middleware so /api/* is not swallowed by the Gradio SPA.
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
from fastapi.encoders import jsonable_encoder
from gradio.routes import App
from starlette.responses import JSONResponse

from api_service import get_health, get_history, get_model_info, get_status

_ORIG_APP_INIT = App.__init__


def _patched_app_init(self, *args, **kwargs):
    _ORIG_APP_INIT(self, *args, **kwargs)

    @self.middleware("http")
    async def floodshield_api(request, call_next):
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"

        try:
            if path == "/api/health":
                return JSONResponse(jsonable_encoder(get_health()))
            if path == "/api/status":
                refresh = request.query_params.get("refresh", "false").lower() in {
                    "1",
                    "true",
                    "yes",
                }
                return JSONResponse(
                    jsonable_encoder(get_status(force_refresh=refresh))
                )
            if path == "/api/history":
                limit = int(request.query_params.get("limit", "30"))
                return JSONResponse(jsonable_encoder(get_history(limit)))
            if path == "/api/model-info":
                return JSONResponse(jsonable_encoder(get_model_info()))
        except FileNotFoundError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=503)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"detail": str(exc)}, status_code=500)

        return await call_next(request)


App.__init__ = _patched_app_init


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
