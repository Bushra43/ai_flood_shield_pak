"""Hugging Face Spaces entrypoint (Gradio + ZeroGPU).

Hugging Face's proxy only forwards /gradio_api/* to Python. The Next.js
dashboard therefore calls those Gradio endpoints, not /api/*.

A tiny @spaces.GPU function is required so ZeroGPU will boot. The real
FloodShield handlers stay on CPU so they do not burn GPU quota.
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

from api_service import get_health, get_history, get_model_info, get_status


@spaces.GPU(duration=10)
def gpu_warmup() -> str:
    return "ok"


def api_health() -> dict:
    return get_health()


def api_status() -> dict:
    return get_status(force_refresh=False)


def api_history() -> list:
    return get_history(30)


def api_model_info() -> dict:
    return get_model_info()


with gr.Blocks(title="AI FloodShield PAK") as demo:
    gr.Markdown(
        """
# AI FloodShield PAK
Chenab River @ Marala — flood-risk API for the dashboard.

`/status` returns day+1 fields (`ml_next_day_risk`, …) plus
`seven_day_outlook` (calendar horizons day +1 … +7).

The Next.js app calls Gradio endpoints:
`/gradio_api/call/health`, `/status`, `/history`, `/model_info`.
        """
    )
    with gr.Row():
        health_btn = gr.Button("Health check")
        status_btn = gr.Button("Current flood status")
    output = gr.JSON(label="Response")
    health_btn.click(fn=api_health, outputs=output, api_name="health")
    status_btn.click(fn=api_status, outputs=output, api_name="status")

    history_btn = gr.Button("History", visible=False)
    model_btn = gr.Button("Model info", visible=False)
    warmup_btn = gr.Button("Warmup", visible=False)
    extra = gr.JSON(visible=False)
    history_btn.click(fn=api_history, outputs=extra, api_name="history")
    model_btn.click(fn=api_model_info, outputs=extra, api_name="model_info")
    warmup_btn.click(fn=gpu_warmup, outputs=extra, api_name="warmup")

demo.queue()
demo.launch(server_name="0.0.0.0", server_port=7860)
