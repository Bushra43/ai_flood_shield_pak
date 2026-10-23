---
title: FloodShield API
emoji: 🌊
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.26.0
app_file: app.py
python_version: "3.12"
pinned: false
short_description: Chenab @ Marala flood-risk API for AI FloodShield PAK
---

# AI FloodShield PAK

Early flood-risk alerting for the **Chenab River at Marala**. The system fuses live official observations, FFD forecasts, and **seven calendar-horizon ML classifiers** (day +1 … +7) into a risk outlook, then phrases bilingual (English / Urdu) community alerts.

**Live API (Hugging Face Space):** [sardar19/floodshield-api](https://huggingface.co/spaces/sardar19/floodshield-api) — `https://sardar19-floodshield-api.hf.space`

## How it works

FloodShield does not replace government warnings. It combines signals and takes the highest credible risk:

1. **Current danger** — official FFD thresholds applied to live inflow / outflow  
2. **FFD 24h forecast** — published quantitative forecast (day +1)  
3. **ML horizon models** — separate classifiers for calendar day +1 … +7  
4. **FFD weekly qualitative outlook** — fused into days +2 … +7 when the date falls in range  

Top-level `ml_next_day_risk` remains the **day +1** class for compatibility. The API also returns `seven_day_outlook` with one card per horizon.

An LLM (Qwen) is used **only to phrase** the already-decided risk level. It cannot change the alert class. If the LLM is unavailable, deterministic templates are used instead.

```text
FFD bulletin / local CSV  →  risk fusion + 7-day outlook  →  English + Urdu alert  →  FastAPI / Gradio  →  Next.js dashboard
```

| Path | Role |
|------|------|
| `backend/` | FastAPI API + decision engine (HF-ready) |
| `frontend/` | Next.js dashboard (Gradio client for Hugging Face Space) |
| `ml/` | Training pipeline, processed data, horizon models |
| `app.py` | Hugging Face Spaces Gradio entrypoint |

## Run locally

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional: add DASHSCOPE_API_KEY for Qwen phrasing
uvicorn main:app --reload --port 8000
```

Default mode is `FLOODSHIELD_MODE=local` (CSV + trained models, works offline). Set `FLOODSHIELD_MODE=live` in `backend/.env` to scrape the latest FFD bulletin (falls back to local on failure).

API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Frontend

```bash
cd frontend
cp .env.example .env.local
# set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

If `NEXT_PUBLIC_API_BASE_URL` is empty, the dashboard uses built-in demo data. Unset, it defaults to the deployed Hugging Face Space.

### 3. Retrain (optional)

```bash
pip install -r ml/requirements.txt
python ml/scripts/train_model.py
```

Writes `ml/models/horizons/floodshield_horizon_{1..7}.pkl` and copies horizon-1 to `ml/models/floodshield_marala_model.pkl`.

## Hugging Face Space

Root [`app.py`](app.py) exposes Gradio APIs the dashboard already calls:

`/gradio_api/call/health`, `/status`, `/history`, `/model_info`

Push this repo (without large raw dumps) to the Space. Ensure `ml/models/horizons/` and `ml/data/processed/` are included. Keep `scikit-learn==1.7.2` pinned in root `requirements.txt` so pickles load.

## Data sources

- [FFD / PMD](https://ffd.pmd.gov.pk/) — daily flood bulletins  
- [PDMA Punjab](https://pdma.punjab.gov.pk/gauge-reports) — gauge & rainfall reports  

## License

Research and demo project for flood early warning at Marala (Chenab).
