---
title: FloodShield API
emoji: 🌊
colorFrom: blue
colorTo: cyan
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
python_version: "3.11"
pinned: false
short_description: Chenab @ Marala flood-risk API for AI FloodShield PAK
---

# AI FloodShield PAK

Early flood-risk alerting for the **Chenab River at Marala**, combining live FFD observations, official thresholds, and a next-day ML risk model into English and Urdu alerts.

**Live API (Hugging Face Space):** [sardar19/floodshield-api](https://huggingface.co/spaces/sardar19/floodshield-api) — `https://sardar19-floodshield-api.hf.space`

## Repository layout

```text
.
├── frontend/   # Next.js web app
├── backend/    # FastAPI API + live FloodShield decision engine
└── ml/         # Dataset pipeline, training, processed data, trained model
```

## How it works

1. **Current danger** — official FFD thresholds on live inflow/outflow  
2. **FFD 24h forecast** — published forecast risk  
3. **ML next-day risk** — Extra Trees / Random Forest model trained on 2024–2025 Marala data  
4. **Final alert** — highest credible risk from the three signals, then phrased in English + Urdu (LLM is used only for wording, not for deciding the level)

## Frontend ↔ backend integration

The dashboard reads from FastAPI when `NEXT_PUBLIC_API_BASE_URL` is set (for example `http://127.0.0.1:8000` locally, or your deployed API URL later). Successful responses are cached in browser `localStorage` so Refresh still works if the API is briefly down.

If the base URL is empty, the app serves built-in local demo data and also writes it to `localStorage`.

Backend default mode is `FLOODSHIELD_MODE=local` (CSV + trained model, no FFD scrape). Set `FLOODSHIELD_MODE=live` when you want the live FFD bulletin path.

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add DASHSCOPE_API_KEY if using Qwen phrasing
uvicorn main:app --reload --port 8000
```

Optional: run the live engine directly:

```bash
cd backend
python floodshield_engine.py
```

### Frontend

```bash
cd frontend
cp .env.example .env.local  # set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### ML pipeline

Raw FFD bulletin PDFs are **not** included in this repository (too large). Processed CSVs and the trained model are under `ml/`.

If you have local PDFs in `ml/data/raw/bulletins/`:

```bash
cd ml
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/extract_data.py      # PDFs → extracted_data.csv
python scripts/final_dataset.py     # derived features
python scripts/build_dataset.py     # Chenab @ Marala filter
python scripts/train_model.py       # train + write ml/models/*.pkl
```

## Data sources

- FFD daily bulletins / advisories: [ffd.pmd.gov.pk](https://ffd.pmd.gov.pk/)
- PDMA gauge reports: [pdma.punjab.gov.pk/gauge-reports](https://pdma.punjab.gov.pk/gauge-reports)
- PDMA rainfall reports: [pdma.punjab.gov.pk/rainfall-reports](https://pdma.punjab.gov.pk/rainfall-reports)

## Marala thresholds (thousand cusecs)

| Level        | Threshold |
|--------------|-----------|
| Low          | 100       |
| Medium       | 150       |
| High         | 200       |
| Very High    | 400       |
| Exceptional  | 600       |
| Design capacity | 1,100  |

## Hugging Face Space

The free Space uses the **Gradio** SDK (not Docker). Root `app.py` wraps FastAPI and still serves `/api/health`, `/api/status`, `/api/history`, `/api/model-info`.

On the Space, add **Secrets** (Settings → Variables and secrets):

- `FLOODSHIELD_MODE` = `local`
- `DASHSCOPE_API_KEY` = your Qwen key
- `DASHSCOPE_BASE_URL` = `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- `CORS_ORIGINS` = your dashboard URL (optional; Vercel/Firebase/HF origins are already allowed)

Then point the frontend at `https://sardar19-floodshield-api.hf.space`.

## Environment

Never commit real API keys. Use:

- `backend/.env.example` → `backend/.env`
- `frontend/.env.example` → `frontend/.env.local`
- Root `.env.example` for reference
- Hugging Face Space secrets for the deployed API

## License / notes

Research and demo project for Pakistan flood early warning at Marala (Chenab).
