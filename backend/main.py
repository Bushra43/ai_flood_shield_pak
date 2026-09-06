from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "AI FloodShield PAK backend is working"
    }


@app.get("/api/status")
def get_status():
    return {
        "date": "2026-09-04",
        "river": "CHENAB",
        "station": "MARALA",
        "current_inflow": 51.9,
        "current_outflow": 26.1,
        "ffd_forecast_min": 100,
        "ffd_forecast_max": 120,
        "ffd_forecast_text": "100 - 120",
        "current_danger": "Normal",
        "ffd_forecast_risk": "Low",
        "ml_next_day_risk": "Normal",
        "ml_confidence": 72.3,
        "final_alert": "Low",
        "english_alert": "Flood risk is currently Low on the Chenab River at Marala.",
        "urdu_alert": "چناب ندی مارالہ پر فلڈ کا خطرہ ابھی کم ہے۔",
        "alert_generated_by": "Qwen"
    }


