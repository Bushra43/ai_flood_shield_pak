# AI FloodShield PAK

Early flood-risk alerting for the **Chenab River at Marala**, combining live FFD observations, official thresholds, and a next-day ML risk model into English and Urdu alerts.

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

## Environment

Never commit real API keys. Use:

- `backend/.env.example` → `backend/.env`
- `frontend/.env.example` → `frontend/.env.local`
- Root `.env.example` for reference

## License / notes

Research and demo project for Pakistan flood early warning at Marala (Chenab).
