# AI FloodShield PAK

Early flood-risk alerting for the **Chenab River at Marala**. The system fuses live official observations, FFD forecasts, and a next-day ML model into a single risk level, then phrases bilingual (English / Urdu) community alerts.

## How it works

FloodShield does not replace government warnings. It combines three signals and takes the highest credible risk:

1. **Current danger** — official FFD thresholds applied to live inflow / outflow  
2. **FFD 24h forecast** — published forecast risk  
3. **ML next-day risk** — Random Forest model trained on Marala historical data  

An LLM (Qwen) is used **only to phrase** the already-decided risk level. It cannot change the alert class. If the LLM is unavailable, deterministic templates are used instead.

```text
FFD bulletin / local CSV  →  risk fusion  →  English + Urdu alert  →  FastAPI  →  Next.js dashboard
```

| Path | Role |
|------|------|
| `backend/` | FastAPI API + decision engine |
| `frontend/` | Next.js dashboard |
| `ml/` | Training pipeline, processed data, trained model |

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

Default mode is `FLOODSHIELD_MODE=local` (CSV + trained model, works offline). Set `FLOODSHIELD_MODE=live` in `backend/.env` to scrape the latest FFD bulletin (falls back to local on failure).

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

If `NEXT_PUBLIC_API_BASE_URL` is empty, the dashboard uses built-in demo data.

## Data sources

- [FFD / PMD](https://ffd.pmd.gov.pk/) — daily flood bulletins  
- [PDMA Punjab](https://pdma.punjab.gov.pk/gauge-reports) — gauge & rainfall reports  

## License

Research and demo project for flood early warning at Marala (Chenab).
