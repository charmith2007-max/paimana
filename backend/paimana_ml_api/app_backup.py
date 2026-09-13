from pathlib import Path
from typing import Any
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# The model was serialized with scikit-learn 1.8.0.
# The API can run under newer versions, but the warning is retained unless
# the model is re-serialized under the exact runtime version.
BASE = Path(__file__).resolve().parent
MODEL = joblib.load(BASE / "paimana_random_forest.joblib")
META = json.loads((BASE / "model_metadata.json").read_text(encoding="utf-8"))
FEATURES = META["features"]

ML_FILE = BASE / "PAIMANA_ML_READY_v1.xlsx"
DF = pd.read_excel(ML_FILE, sheet_name="ML_Features")
DF["report_month_dt"] = pd.to_datetime(DF["report_month"], errors="coerce")

app = FastAPI(title="PAIMANA ML Risk API", version="1.2.0")


class PredictRequest(BaseModel):
    # If project_id is supplied, the API uses that project's latest
    # available ML_Features row. Optional feature overrides can be supplied.
    project_id: str | None = None
    features: dict[str, Any] | None = None


def risk_level(score: float) -> str:
    if score < 30:
        return "Low"
    if score <= 60:
        return "Medium"
    return "High"


def drivers(row: pd.Series) -> list[str]:
    vals = []

    def add(label, severity):
        vals.append((severity, label))

    if pd.notna(row.get("schedule_shift_since_previous_month")) and row["schedule_shift_since_previous_month"] > 0:
        add("Anticipated completion moved later vs previous report", 4)
    if pd.notna(row.get("months_original_schedule_slippage")) and row["months_original_schedule_slippage"] > 12:
        add("Large schedule slippage vs original plan", 3)
    if pd.notna(row.get("current_cost_overrun_pct")) and row["current_cost_overrun_pct"] > 10:
        add("Current cost overrun is elevated", 3)
    if pd.notna(row.get("anticipated_cost_change_pct")) and row["anticipated_cost_change_pct"] > 5:
        add("Anticipated cost increased vs previous report", 2)
    if pd.notna(row.get("physical_progress_change")) and row["physical_progress_change"] < 0:
        add("Physical progress declined vs previous report", 2)
    if (
        pd.notna(row.get("months_to_anticipated_completion"))
        and row["months_to_anticipated_completion"] <= 6
        and (pd.isna(row.get("physical_progress")) or row.get("physical_progress", 0) < 90)
    ):
        add("Near anticipated completion with limited progress", 2)
    if row.get("additional_delay_flag", 0) == 1:
        add("Project has an additional-delay signal", 4)
    if pd.notna(row.get("expenditure_vs_anticipated_cost_pct")) and row["expenditure_vs_anticipated_cost_pct"] > 90:
        add("Expenditure is high relative to anticipated cost", 1)

    return [x[1] for x in sorted(vals, reverse=True)[:3]] or ["No strong rule-based warning flag"]


def predict_row(row: pd.Series) -> dict:
    x = pd.DataFrame([{f: row.get(f, np.nan) for f in FEATURES}])
    probability = float(MODEL.predict_proba(x)[:, 1][0])
    score = round(probability * 100, 1)

    report_month = row.get("report_month")
    report_month = None if pd.isna(report_month) else str(report_month)

    return {
        "project_id": str(row.get("project_id", "")),
        "project_name": None if pd.isna(row.get("project_name")) else row.get("project_name"),
        "agency": None if pd.isna(row.get("agency")) else row.get("agency"),
        "state": None if pd.isna(row.get("state")) else row.get("state"),
        "report_month": report_month,
        "delay_probability": round(probability, 4),
        "risk_score_100": score,
        "risk_level": risk_level(score),
        "top_risk_drivers": drivers(row),
        "interpretation": "Model-estimated probability of next-month additional delay; drivers are rule-based warning flags, not causal explanations.",
    }


@app.get("/")
def root():
    return {
        "service": "PAIMANA ML Risk API",
        "status": "ok",
        "docs": "/docs",
        "version": "1.2.0",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": META["model"],
        "training_scope": META["training_scope"],
    }


@app.get("/model-info")
def model_info():
    return META


@app.get("/projects")
def projects(limit: int = 20, risk_level_filter: str | None = None):
    latest = (
        DF.sort_values(["project_id", "report_month_dt"])
        .groupby("project_id", as_index=False)
        .tail(1)
        .copy()
    )
    probs = MODEL.predict_proba(latest[FEATURES])[:, 1]
    latest["risk_score_100"] = probs * 100
    latest["risk_level"] = latest["risk_score_100"].apply(risk_level)

    if risk_level_filter:
        latest = latest[latest["risk_level"].str.lower() == risk_level_filter.lower()]

    latest = latest.sort_values("risk_score_100", ascending=False).head(max(1, min(limit, 500)))
    return {
        "count": len(latest),
        "projects": [predict_row(r) for _, r in latest.iterrows()],
    }


@app.get("/projects/{project_id}")
def project(project_id: str):
    rows = DF[DF.project_id.astype(str) == project_id].sort_values("report_month_dt")
    if rows.empty:
        raise HTTPException(status_code=404, detail="Project ID not found")

    history = [predict_row(r) for _, r in rows.iterrows()]
    return {
        "project_id": project_id,
        "observation_count": len(rows),
        "history": history,
        "latest": history[-1],
    }


@app.post("/predict")
def predict(req: PredictRequest):
    # Preferred path: send only project_id and let the API use the latest
    # feature row for that project.
    if req.project_id:
        rows = DF[DF.project_id.astype(str) == req.project_id].sort_values("report_month_dt")
        if rows.empty:
            raise HTTPException(status_code=404, detail="Project ID not found")
        row = rows.iloc[-1].copy()
        if req.features:
            for key, value in req.features.items():
                row[key] = value
        result = predict_row(row)
        result["prediction_source"] = "latest_project_row"
        result["missing_features_supplied"] = [
            f for f in FEATURES if f not in (req.features or {})
        ]
        return result

    # Backward-compatible path: accept a raw feature payload.
    if req.features:
        row = pd.Series(req.features)
        result = predict_row(row)
        result["prediction_source"] = "supplied_features"
        result["missing_features_supplied"] = [f for f in FEATURES if f not in req.features]
        return result

    raise HTTPException(status_code=422, detail="Provide either project_id or features")