from pathlib import Path
from typing import Any
import json
import os

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client
from agents.ingestion_agent import IngestionAgent
from agents.ml_agent import MLAgent
from agents.agent3 import Agent3UpdateAgent
from agents.agent4 import Agent4PrescriptionAgent

# ============================================================
# CONFIGURATION
# ============================================================

BASE = Path(__file__).resolve().parent

load_dotenv(BASE / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


# ============================================================
# ML MODEL
# ============================================================

MODEL = joblib.load(BASE / "paimana_random_forest.joblib")

META = json.loads(
    (BASE / "model_metadata.json").read_text(encoding="utf-8")
)

FEATURES = META["features"]


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="PAIMANA ML Risk API",
    version="1.3.0",
)

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


# ============================================================
# REQUEST MODEL
# ============================================================

class PredictRequest(BaseModel):
    project_id: str | None = None
    features: dict[str, Any] | None = None


# ============================================================
# HELPERS
# ============================================================

def fetch_all(table: str, columns: str = "*") -> list[dict]:
    """
    Supabase Data API normally returns a limited number of rows.
    Fetch in batches so the API can safely retrieve larger tables.
    """

    rows = []
    start = 0
    batch_size = 1000

    while True:
        response = (
            supabase
            .table(table)
            .select(columns)
            .range(start, start + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < batch_size:
            break

        start += batch_size

    return rows


def fetch_project(project_id: str) -> dict | None:
    response = (
        supabase
        .table("projects")
        .select("*")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def fetch_project_months(project_id: str) -> list[dict]:
    response = (
        supabase
        .table("project_months")
        .select("*")
        .eq("project_id", project_id)
        .order("report_month", desc=False)
        .execute()
    )

    return response.data or []


def fetch_project_features(project_id: str) -> list[dict]:
    response = (
        supabase
        .table("ml_features")
        .select("*")
        .eq("project_id", project_id)
        .order("report_month", desc=False)
        .execute()
    )

    return response.data or []


def build_project_history(project_id: str) -> pd.DataFrame:
    """
    Combines:
      projects
      project_months
      ml_features

    into the feature rows expected by the Random Forest.
    """

    project = fetch_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project ID not found",
        )

    month_rows = fetch_project_months(project_id)

    if not month_rows:
        raise HTTPException(
            status_code=404,
            detail="No project-month records found",
        )

    feature_rows = fetch_project_features(project_id)

    months = pd.DataFrame(month_rows)

    if feature_rows:
        features = pd.DataFrame(feature_rows)

        # Avoid duplicate project/report_month columns during merge.
        merge_cols = [
            c for c in features.columns
            if c not in ["project_id"]
        ]

        months = months.merge(
            features[merge_cols],
            on="report_month",
            how="left",
        )

    # Add project identity.
    months["project_name"] = project.get("project_name")
    months["agency"] = project.get("agency")
    months["state"] = project.get("state")

    months["report_month_dt"] = pd.to_datetime(
        months["report_month"],
        errors="coerce",
    )

    months = months.sort_values("report_month_dt")

    return months


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

    if (
        pd.notna(row.get("schedule_shift_since_previous_month"))
        and row["schedule_shift_since_previous_month"] > 0
    ):
        add(
            "Anticipated completion moved later vs previous report",
            4,
        )

    if (
        pd.notna(row.get("months_original_schedule_slippage"))
        and row["months_original_schedule_slippage"] > 12
    ):
        add(
            "Large schedule slippage vs original plan",
            3,
        )

    if (
        pd.notna(row.get("current_cost_overrun_pct"))
        and row["current_cost_overrun_pct"] > 10
    ):
        add(
            "Current cost overrun is elevated",
            3,
        )

    if (
        pd.notna(row.get("anticipated_cost_change_pct"))
        and row["anticipated_cost_change_pct"] > 5
    ):
        add(
            "Anticipated cost increased vs previous report",
            2,
        )

    if (
        pd.notna(row.get("physical_progress_change"))
        and row["physical_progress_change"] < 0
    ):
        add(
            "Physical progress declined vs previous report",
            2,
        )

    if (
        pd.notna(row.get("months_to_anticipated_completion"))
        and row["months_to_anticipated_completion"] <= 6
        and (
            pd.isna(row.get("physical_progress"))
            or row.get("physical_progress", 0) < 90
        )
    ):
        add(
            "Near anticipated completion with limited progress",
            2,
        )

    if row.get("additional_delay_flag", 0) == 1:
        add(
            "Project has an additional-delay signal",
            4,
        )

    if (
        pd.notna(row.get("expenditure_vs_anticipated_cost_pct"))
        and row["expenditure_vs_anticipated_cost_pct"] > 90
    ):
        add(
            "Expenditure is high relative to anticipated cost",
            1,
        )

    return [
        x[1]
        for x in sorted(vals, reverse=True)[:3]
    ] or [
        "No strong rule-based warning flag"
    ]


def nullable_number(row: pd.Series, key: str) -> float | None:
    if key not in row.index:
        return None

    value = row[key]

    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def nullable_text(row: pd.Series, key: str) -> str | None:
    if key not in row.index:
        return None

    value = row[key]

    if value is None or pd.isna(value):
        return None

    return str(value)


def prepare_model_input(row: pd.Series) -> pd.DataFrame:
    """
    Create exactly the 25 features expected by the trained model.
    """

    data = {}

    for feature in FEATURES:
        value = row.get(feature, np.nan)

        if pd.isna(value):
            data[feature] = np.nan
        else:
            data[feature] = value

    x = pd.DataFrame([data])

    # Numeric columns used by the model.
    categorical = {
        "agency",
        "state",
        "delay_reason_category",
    }

    for feature in FEATURES:
        if feature not in categorical:
            x[feature] = pd.to_numeric(
                x[feature],
                errors="coerce",
            )

    return x


def predict_row(row: pd.Series) -> dict:
    x = prepare_model_input(row)

    probability = float(
        MODEL.predict_proba(x)[:, 1][0]
    )

    score = round(probability * 100, 1)

    report_month = row.get("report_month")

    if pd.isna(report_month):
        report_month = None
    else:
        report_month = str(report_month)

    return {
        "project_id": str(
            row.get("project_id", "")
        ),

        "project_name": (
            None
            if pd.isna(row.get("project_name"))
            else row.get("project_name")
        ),

        "agency": (
            None
            if pd.isna(row.get("agency"))
            else row.get("agency")
        ),

        "state": (
            None
            if pd.isna(row.get("state"))
            else row.get("state")
        ),

        "report_month": report_month,

        "delay_probability": round(
            probability,
            4,
        ),

        "risk_score_100": score,

        "risk_level": risk_level(score),

        "top_risk_drivers": drivers(row),

        "interpretation": (
            "Model-estimated probability of next-month "
            "additional delay; drivers are rule-based "
            "warning flags, not causal explanations."
        ),

        "original_cost": nullable_number(row, "original_cost"),
        "revised_cost": nullable_number(row, "revised_cost"),
        "anticipated_cost": nullable_number(row, "anticipated_cost"),
        "expenditure": nullable_number(row, "expenditure"),
        "physical_progress": nullable_number(row, "physical_progress"),
        "time_overrun": nullable_number(row, "time_overrun"),
        "cost_overrun": nullable_number(row, "cost_overrun"),
        "original_completion": nullable_text(row, "original_completion"),
        "revised_completion": nullable_text(row, "revised_completion"),
        "anticipated_completion": nullable_text(row, "anticipated_completion"),
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "service": "PAIMANA ML Risk API",
        "status": "ok",
        "docs": "/docs",
        "version": "1.3.0",
        "database": "Supabase",
    }


@app.get("/health")
def health():
    """
    Health check including Supabase connectivity.
    """

    try:
        response = (
            supabase
            .table("projects")
            .select("project_id")
            .limit(1)
            .execute()
        )

        database_status = (
            "connected"
            if response.data is not None
            else "error"
        )

    except Exception as e:
        database_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": database_status,
        "model": META["model"],
        "training_scope": META["training_scope"],
    }


@app.get("/model-info")
def model_info():
    return META


@app.get("/projects")
def projects(
    limit: int = 20,
    risk_level_filter: str | None = None,
):
    """
    Return current portfolio risk using the precomputed
    project_risk table instead of recalculating every project.
    """

    limit = max(1, min(limit, 2000))

    project_rows = fetch_all(
        "projects",
        "project_id,project_name,agency,state",
    )

    risk_rows = fetch_all(
        "project_risk",
        "project_id,report_month,model_delay_probability,"
        "risk_score_100,risk_level,top_risk_drivers,"
        "risk_interpretation,prediction_source",
    )

    if not project_rows or not risk_rows:
        return {
            "count": 0,
            "projects": [],
        }

    project_map = {
        str(p["project_id"]): p
        for p in project_rows
    }

    results = []

    for risk in risk_rows:
        project_id = str(risk["project_id"])
        project = project_map.get(project_id)

        if not project:
            continue

        risk_level = str(
            risk.get("risk_level") or ""
        )

        if (
            risk_level_filter
            and risk_level.lower()
            != risk_level_filter.lower()
        ):
            continue

        results.append({
            "project_id": project_id,
            "project_name": project["project_name"],
            "agency": project["agency"],
            "state": project["state"],
            "report_month": risk["report_month"],
            "delay_probability": float(
                risk["model_delay_probability"] or 0
            ),
            "risk_score_100": float(
                risk["risk_score_100"] or 0
            ),
            "risk_level": risk_level,
            "top_risk_drivers": risk.get(
                "top_risk_drivers"
            ),
            "risk_interpretation": risk.get(
                "risk_interpretation"
            ),
            "prediction_source": risk.get(
                "prediction_source"
            ),
        })

    results.sort(
        key=lambda r: r["risk_score_100"],
        reverse=True,
    )

    results = results[:limit]

    return {
        "count": len(results),
        "projects": results,
    }


@app.get("/projects/{project_id}")
def project(project_id: str):
    """
    Return complete project history.

    The historical rows use their normal predictions.
    The latest risk is taken from the precomputed project_risk
    table for consistency with the portfolio page.
    """

    history_df = build_project_history(project_id)

    if history_df.empty:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    history = [
        predict_row(row)
        for _, row in history_df.iterrows()
    ]

    # Fetch only this project's precomputed risk rows.
    response = (
        supabase
        .table("project_risk")
        .select(
            "project_id,report_month,model_delay_probability,"
            "risk_score_100,risk_level,top_risk_drivers,"
            "risk_interpretation,prediction_source"
        )
        .eq("project_id", project_id)
        .order("report_month", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        latest_risk = response.data[0]
        latest = history[-1]

        latest["delay_probability"] = float(
            latest_risk["model_delay_probability"] or 0
        )
        latest["risk_score_100"] = float(
            latest_risk["risk_score_100"] or 0
        )
        latest["risk_level"] = latest_risk["risk_level"]
        drivers = latest_risk.get("top_risk_drivers")

        if isinstance(drivers, str):
            latest["top_risk_drivers"] = [drivers]
        elif isinstance(drivers, list):
            latest["top_risk_drivers"] = drivers
        else:
            latest["top_risk_drivers"] = []
        latest["risk_interpretation"] = latest_risk.get(
            "risk_interpretation"
        )
        latest["prediction_source"] = latest_risk.get(
            "prediction_source"
        )

        history[-1] = latest

    return {
        "project_id": project_id,
        "observation_count": len(history),
        "history": history,
        "latest": history[-1],
    }
@app.post("/agent/ingest")
async def agent_ingest(
    file: UploadFile = File(...),
    report_month: str | None = Form(None),
):
    """
    Agent 1:
    PDF -> project records -> DRAFT staging dataset.
    """

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF Flash Reports are supported."
        )

    upload_dir = BASE / "agent_uploads"
    upload_dir.mkdir(exist_ok=True)

    pdf_path = upload_dir / file.filename
    contents = await file.read()
    pdf_path.write_bytes(contents)

    agent = IngestionAgent()

    # If officer explicitly supplied a valid report_month (YYYY-MM), use it.
    final_report_month = None
    if report_month and report_month.strip():
        m_str = report_month.strip()
        # Normalize if YYYY-MM-DD was provided
        if len(m_str) >= 7 and m_str[:4].isdigit() and m_str[5:7].isdigit():
            final_report_month = m_str[:7]

    if not final_report_month:
        try:
            final_report_month = agent.detect_report_month(
                file.filename,
                pdf_path=pdf_path,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

    # Create DRAFT.
    run_response = (
        supabase
        .table("ingestion_runs")
        .insert({
            "filename": file.filename,
            "report_month": f"{final_report_month}-01",
            "status": "DRAFT",
            "notes": "Uploaded by officer."
        })
        .execute()
    )

    if not run_response.data:
        raise HTTPException(
            status_code=500,
            detail="Could not create ingestion draft."
        )

    run = run_response.data[0]

    try:
        rows = agent.extract_project_rows(
            pdf_path,
            final_report_month,
            file.filename
        )

        if not rows:
            raise ValueError(
                "No project records could be extracted."
            )

        # Insert extracted rows into staging.
        supabase.table("ingestion_records").insert(
            [
                {
                    key: value
                    for key, value in row.items()
                    if value is not None
                }
                | {
                    "ingestion_run_id": run["id"]
                }
                for row in rows
            ]
        ).execute()

        # Update DRAFT summary.
        supabase.table("ingestion_runs").update({
            "row_count": len(rows),
            "accepted_rows": len(rows),
            "notes": (
                f"Extracted {len(rows)} project records. "
                "Awaiting officer review."
            )
        }).eq(
            "id",
            run["id"]
        ).execute()

    except Exception as e:

        supabase.table("ingestion_runs").update({
            "status": "FAILED",
            "notes": f"Extraction failed: {str(e)}"
        }).eq(
            "id",
            run["id"]
        ).execute()

        raise HTTPException(
            status_code=500,
            detail=f"Project extraction failed: {str(e)}"
        )

    return {
        "agent": "PAIMANA Ingestion Agent",
        "status": "DRAFT",
        "ingestion_run_id": run["id"],
        "filename": file.filename,
        "report_month": report_month,
        "extracted_projects": len(rows),
        "message": (
            "Flash Report extracted successfully. "
            "Records are stored as DRAFT and are NOT "
            "available to ML prediction."
        ),
        "next_stage": "officer_review"
    }
@app.delete("/agent/ingest/{ingestion_run_id}")
def delete_ingestion(ingestion_run_id: int):
    """
    Delete an ingestion draft.

    Only DRAFT or FAILED runs can be deleted.
    Approved data is never deleted through this endpoint.
    """

    response = (
        supabase
        .table("ingestion_runs")
        .select("id,status,filename")
        .eq("id", ingestion_run_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion run not found."
        )

    run = response.data[0]
    status = str(run.get("status", "")).upper()

    if status not in {"DRAFT", "FAILED", "REJECTED"}:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete ingestion run with status "
                f"'{status}'. Only DRAFT, FAILED, or REJECTED "
                f"runs can be deleted."
            )
        )

    (
        supabase
        .table("ingestion_runs")
        .delete()
        .eq("id", ingestion_run_id)
        .execute()
    )

    # Remove the uploaded PDF from local storage too.
    pdf_path = BASE / "agent_uploads" / str(run["filename"])

    if pdf_path.exists():
        pdf_path.unlink()

    return {
        "status": "deleted",
        "ingestion_run_id": ingestion_run_id,
        "filename": run["filename"],
        "message": (
            "Draft report and all associated extracted records "
            "were deleted. It will not be used for ML prediction."
        )
    }
@app.post("/predict")
def predict(req: PredictRequest):
    """
    Preferred:
        {"project_id": "220100184"}

    Optional feature overrides are supported.
    """

    if req.project_id:

        history_df = build_project_history(
            req.project_id
        )

        if history_df.empty:
            raise HTTPException(
                status_code=404,
                detail="Project ID not found",
            )

        row = history_df.iloc[-1].copy()

        if req.features:
            for key, value in req.features.items():
                row[key] = value

        result = predict_row(row)

        result["prediction_source"] = (
            "latest_project_row_supabase"
        )

        result["missing_features_supplied"] = [
            feature
            for feature in FEATURES
            if feature not in (req.features or {})
        ]

        return result

    # Backward-compatible raw feature prediction.
    if req.features:

        row = pd.Series(req.features)

        result = predict_row(row)

        result["prediction_source"] = (
            "supplied_features"
        )

        result["missing_features_supplied"] = [
            feature
            for feature in FEATURES
            if feature not in req.features
        ]

        return result

    raise HTTPException(
        status_code=422,
        detail=(
            "Provide either project_id or features"
        ),
    )
@app.get("/agent/ingest")
def list_ingestion_runs():
    response = (
        supabase.table("ingestion_runs")
        .select("*")
        .order("uploaded_at", desc=True)
        .execute()
    )

    return {
        "runs": response.data or []
    }
@app.get("/agent/ingest/{ingestion_run_id}")
def get_ingestion_run(ingestion_run_id: int, limit: int = 100, offset: int = 0):
    run_response = (
        supabase.table("ingestion_runs")
        .select("*")
        .eq("id", ingestion_run_id)
        .limit(1)
        .execute()
    )

    if not run_response.data:
        raise HTTPException(status_code=404, detail="Ingestion run not found.")

    run = run_response.data[0]

    records_response = (
        supabase.table("ingestion_records")
        .select("*")
        .eq("ingestion_run_id", ingestion_run_id)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {
        "run": run,
        "records": records_response.data or [],
        "limit": limit,
        "offset": offset,
    }
@app.put("/agent/ingest/{ingestion_run_id}/records/{record_id}")
def update_ingestion_record(
    ingestion_run_id: int,
    record_id: int,
    updates: dict,
):
    # Check that the ingestion run exists and is still editable
    run_response = (
        supabase.table("ingestion_runs")
        .select("id,status")
        .eq("id", ingestion_run_id)
        .limit(1)
        .execute()
    )

    if not run_response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion run not found."
        )

    status = str(run_response.data[0].get("status", "")).upper()

    if status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only DRAFT ingestion runs can be edited."
        )

    allowed_fields = {
        "project_id",
        "project_name",
        "agency",
        "state",
        "original_cost",
        "revised_cost",
        "anticipated_cost",
        "expenditure",
        "original_completion",
        "revised_completion",
        "anticipated_completion",
        "physical_progress",
        "time_overrun",
        "cost_overrun",
        "delay_reason",
        "is_delayed",
        "additional_delay_flag",
        "additional_delay_months",
        "delay_reason_category",
    }

    clean_updates = {
        key: value
        for key, value in updates.items()
        if key in allowed_fields
    }

    if not clean_updates:
        raise HTTPException(
            status_code=400,
            detail="No editable fields supplied."
        )

    response = (
        supabase.table("ingestion_records")
        .update(clean_updates)
        .eq("id", record_id)
        .eq("ingestion_run_id", ingestion_run_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion record not found."
        )

    return {
        "status": "updated",
        "ingestion_run_id": ingestion_run_id,
        "record_id": record_id,
        "record": response.data[0],
        "message": "Draft record updated successfully."
    }
@app.delete("/agent/ingest/{ingestion_run_id}/records/{record_id}")
def delete_ingestion_record(
    ingestion_run_id: int,
    record_id: int,
):
    run_response = (
        supabase.table("ingestion_runs")
        .select("id,status")
        .eq("id", ingestion_run_id)
        .limit(1)
        .execute()
    )

    if not run_response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion run not found."
        )

    status = str(run_response.data[0].get("status", "")).upper()

    if status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only DRAFT ingestion runs can be edited."
        )

    response = (
        supabase.table("ingestion_records")
        .delete()
        .eq("id", record_id)
        .eq("ingestion_run_id", ingestion_run_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion record not found."
        )

    # Keep the draft run count synchronized
    count_response = (
        supabase.table("ingestion_records")
        .select("id", count="exact")
        .eq("ingestion_run_id", ingestion_run_id)
        .execute()
    )

    remaining = count_response.count or 0

    supabase.table("ingestion_runs").update({
        "row_count": remaining,
        "accepted_rows": remaining,
        "notes": f"{remaining} project records remain after officer review."
    }).eq("id", ingestion_run_id).execute()

    return {
        "status": "deleted",
        "ingestion_run_id": ingestion_run_id,
        "record_id": record_id,
        "remaining_records": remaining,
        "message": "Draft record deleted successfully and will not be used by ML."
    }
@app.post("/agent/ingest/{ingestion_run_id}/approve")
def approve_ingestion(ingestion_run_id: int):
    """
    Approve a DRAFT ingestion and run Agent 2.

    If Agent 2 fails, the production rows written by this approval
    are rolled back using the full-row backup created by the
    approve_ingestion_transaction PostgreSQL function.
    """

    import traceback

    # 1. Get the draft
    run_response = (
        supabase.table("ingestion_runs")
        .select("*")
        .eq("id", ingestion_run_id)
        .limit(1)
        .execute()
    )

    if not run_response.data:
        raise HTTPException(
            status_code=404,
            detail="Ingestion run not found.",
        )

    run = run_response.data[0]

    if str(run.get("status", "")).upper() != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only DRAFT ingestion runs can be approved.",
        )

    # 2. Load and validate draft records
    records = []
    start = 0
    batch_size = 1000

    while True:
        response = (
            supabase.table("ingestion_records")
            .select("*")
            .eq("ingestion_run_id", ingestion_run_id)
            .range(start, start + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        records.extend(batch)

        if len(batch) < batch_size:
            break

        start += batch_size

    if not records:
        raise HTTPException(
            status_code=400,
            detail="Cannot approve an empty ingestion draft.",
        )

    required_fields = [
        "project_id",
        "project_name",
        "agency",
        "state",
        "report_month",
    ]

    invalid_records = []

    for record in records:
        missing = [
            field
            for field in required_fields
            if not record.get(field)
        ]

        if missing:
            invalid_records.append({
                "record_id": record.get("id"),
                "project_id": record.get("project_id"),
                "missing_fields": missing,
            })

    if invalid_records:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Draft contains records requiring correction.",
                "invalid_records": invalid_records[:25],
                "invalid_count": len(invalid_records),
            },
        )

    # 3. Move the draft into production through PostgreSQL.
    try:
        rpc_response = supabase.rpc(
            "approve_ingestion_transaction",
            {"p_ingestion_run_id": ingestion_run_id},
        ).execute()

        if not rpc_response.data:
            raise RuntimeError(
                "Approval transaction returned no result."
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database approval failed: {str(e)}",
        )

    # 4. Agent 2
    try:
        ml_agent = MLAgent()

        approved_ids = list(dict.fromkeys(
            str(record["project_id"]).strip()
            for record in records
            if record.get("project_id") is not None
        ))

        if not approved_ids:
            raise RuntimeError(
                "No approved project IDs found for Agent 2."
            )

        # Fetch project history in small ID batches and paginate each
        # request so the Supabase/PostgREST row limit cannot silently
        # truncate the result.
        history_rows = []
        project_batch_size = 200
        history_page_size = 1000

        for i in range(0, len(approved_ids), project_batch_size):
            batch_ids = approved_ids[
                i:i + project_batch_size
            ]

            page_start = 0

            while True:
                response = (
                    supabase
                    .table("project_months")
                    .select("*")
                    .in_("project_id", batch_ids)
                    .range(
                        page_start,
                        page_start + history_page_size - 1,
                    )
                    .execute()
                )

                batch = response.data or []

                if not batch:
                    break

                history_rows.extend(batch)

                if len(batch) < history_page_size:
                    break

                page_start += history_page_size

        if not history_rows:
            raise RuntimeError(
                "No project history found for approved projects."
            )

        project_history = pd.DataFrame(history_rows)

        if "project_id" not in project_history.columns:
            raise RuntimeError(
                "project_months response is missing project_id."
            )

        if "report_month" not in project_history.columns:
            raise RuntimeError(
                "project_months response is missing report_month."
            )

        project_history["project_id"] = (
            project_history["project_id"]
            .astype(str)
            .str.strip()
        )

        project_history["report_month"] = pd.to_datetime(
            project_history["report_month"],
            errors="coerce",
        )

        project_history = project_history[
            project_history["report_month"].notna()
        ].copy()

        if project_history.empty:
            raise RuntimeError(
                "Project history contains no valid report months."
            )

        # --------------------------------------------------------
        # project_months contains the monthly numerical/project
        # status fields, but agency/state belong to the projects
        # table. Agent 2's trained model expects both categorical
        # columns, so attach them before feature generation.
        # --------------------------------------------------------

        project_rows = []
        project_page_size = 1000

        for i in range(0, len(approved_ids), 500):
            batch_ids = approved_ids[i:i + 500]

            project_response = (
                supabase
                .table("projects")
                .select("project_id,project_name,agency,state")
                .in_("project_id", batch_ids)
                .range(0, project_page_size - 1)
                .execute()
            )

            project_rows.extend(
                project_response.data or []
            )

        if not project_rows:
            raise RuntimeError(
                "No project identity records found for approved projects."
            )

        projects_df = pd.DataFrame(project_rows)

        if "project_id" not in projects_df.columns:
            raise RuntimeError(
                "projects response is missing project_id."
            )

        projects_df["project_id"] = (
            projects_df["project_id"]
            .astype(str)
            .str.strip()
        )

        # Keep one identity row per project.
        projects_df = (
            projects_df
            .drop_duplicates(
                subset=["project_id"],
                keep="last",
            )
        )

        project_history = project_history.merge(
            projects_df[
                [
                    "project_id",
                    "project_name",
                    "agency",
                    "state",
                ]
            ],
            on="project_id",
            how="left",
            suffixes=("", "_project"),
        )

        # If a monthly table ever contains these columns itself,
        # prefer the monthly value; otherwise use projects.
        for column in ["project_name", "agency", "state"]:
            project_column = f"{column}_project"

            if project_column in project_history.columns:
                if column in project_history.columns:
                    project_history[column] = (
                        project_history[column]
                        .where(
                            project_history[column].notna(),
                            project_history[project_column],
                        )
                    )
                    project_history.drop(
                        columns=[project_column],
                        inplace=True,
                    )
                else:
                    project_history.rename(
                        columns={
                            project_column: column
                        },
                        inplace=True,
                    )

        missing_identity = project_history[
            project_history["agency"].isna()
            | project_history["state"].isna()
        ][
            ["project_id", "agency", "state"]
        ].drop_duplicates()

        if not missing_identity.empty:
            raise RuntimeError(
                "Project identity data is missing agency/state for "
                f"{len(missing_identity)} projects. "
                f"Examples={missing_identity.head(10).to_dict('records')}"
            )

        history_project_ids = set(
            project_history["project_id"].unique()
        )

        missing_history_ids = [
            project_id
            for project_id in approved_ids
            if project_id not in history_project_ids
        ]

        print("\n========== AGENT 2 INPUT ==========")
        print("Approved projects:", len(approved_ids))
        print("History rows:", len(project_history))
        print("Projects with history:", len(history_project_ids))
        print("Projects missing history:", len(missing_history_ids))

        if missing_history_ids:
            print(
                "First missing IDs:",
                missing_history_ids[:20],
            )

        print("===================================\n")

        # 5. Run Agent 2 project by project.
        predictions = []
        failed_projects = []

        for project_id in approved_ids:
            history_df = project_history[
                project_history["project_id"] == project_id
            ].copy()

            if history_df.empty:
                failed_projects.append({
                    "project_id": project_id,
                    "error": "No project history returned.",
                })
                continue

            history_df = (
                history_df
                .sort_values("report_month")
                .reset_index(drop=True)
            )

            try:
                agent_result = ml_agent.run_from_history(
                    history_df
                )

                feature_predictions = agent_result.get(
                    "predictions"
                )

                if feature_predictions is None:
                    raise RuntimeError(
                        "Agent 2 returned no predictions dataframe."
                    )

                if feature_predictions.empty:
                    raise RuntimeError(
                        "Agent 2 returned zero prediction rows."
                    )

                latest_prediction = (
                    feature_predictions
                    .sort_values("report_month")
                    .iloc[-1]
                )

                probability = float(
                    latest_prediction[
                        "model_delay_probability"
                    ]
                )

                score = float(
                    latest_prediction[
                        "risk_score_100"
                    ]
                )

                level = str(
                    latest_prediction["risk_level"]
                )

                # Existing PAIMANA explanation logic.
                try:
                    explanation = predict_row(
                        latest_prediction
                    )

                    risk_drivers = explanation.get(
                        "top_risk_drivers",
                        [],
                    )

                    interpretation = explanation.get(
                        "interpretation"
                    )

                except Exception:
                    risk_drivers = [
                        (
                            "Model-estimated risk based on "
                            "current project features"
                        )
                    ]

                    interpretation = (
                        "Model-estimated probability of "
                        "next-month additional delay."
                    )

                if isinstance(risk_drivers, str):
                    risk_drivers = [risk_drivers]

                report_month = pd.to_datetime(
                    latest_prediction["report_month"],
                    errors="coerce",
                )

                if pd.isna(report_month):
                    raise RuntimeError(
                        "Agent 2 produced an invalid report_month."
                    )

                predictions.append({
                    "project_id": str(project_id),
                    "report_month": str(report_month.date()),
                    "model_delay_probability": probability,
                    "risk_score_100": score,
                    "risk_level": level,
                    "top_risk_drivers": risk_drivers,
                    "risk_interpretation": interpretation,
                    "prediction_source": (
                        "Agent 2 - Approved Flash Report"
                    ),
                })

            except Exception as project_error:
                failed_projects.append({
                    "project_id": project_id,
                    "error": str(project_error),
                })

        # 6. Never leave a partially predicted approval.
        prediction_project_ids = {
            str(row["project_id"])
            for row in predictions
        }

        missing_prediction_ids = [
            project_id
            for project_id in approved_ids
            if project_id not in prediction_project_ids
        ]

        if missing_prediction_ids:
            raise RuntimeError(
                "Agent 2 did not generate predictions for all "
                f"approved projects. "
                f"Approved={len(approved_ids)}, "
                f"Predicted={len(predictions)}, "
                f"Missing={len(missing_prediction_ids)}. "
                f"Examples={failed_projects[:10]}"
            )

        # 7. Save project-risk predictions in batches.
        for i in range(0, len(predictions), 500):
            (
                supabase
                .table("project_risk")
                .upsert(
                    predictions[i:i + 500],
                    on_conflict="project_id,report_month",
                )
                .execute()
            )

        # 8. Final success.
        (
            supabase
            .table("ingestion_runs")
            .update({
                "status": "APPROVED",
                "notes": (
                    f"Officer approved {len(records)} records. "
                    f"Agent 2 generated {len(predictions)} "
                    "risk predictions."
                ),
            })
            .eq("id", ingestion_run_id)
            .execute()
        )

        return {
            "status": "APPROVED",
            "ingestion_run_id": ingestion_run_id,
            "records_approved": len(records),
            "predictions_generated": len(predictions),
            "projects_with_history": len(history_project_ids),
            "projects_missing_history": len(missing_history_ids),
            "agent": "PAIMANA ML Agent",
            "message": (
                "Flash Report approved successfully. "
                "Agent 2 created ML features and "
                "updated risk predictions."
            ),
        }

    # 9. Agent 2 failure -> rollback.
    except Exception as e:
        error_message = str(e)

        print("\n========== AGENT 2 FAILURE ==========")
        print(error_message)
        traceback.print_exc()
        print("======================================\n")

        try:
            backup_response = (
                supabase
                .table("ingestion_approval_backup")
                .select(
                    "project_id,"
                    "report_month,"
                    "previous_row,"
                    "row_existed"
                )
                .eq(
                    "ingestion_run_id",
                    ingestion_run_id,
                )
                .execute()
            )

            backup_rows = backup_response.data or []

            # Remove predictions created for this approval.
            for item in backup_rows:
                (
                    supabase
                    .table("project_risk")
                    .delete()
                    .eq("project_id", item["project_id"])
                    .eq("report_month", item["report_month"])
                    .execute()
                )

            # Remove the current project-month version.
            for item in backup_rows:
                (
                    supabase
                    .table("project_months")
                    .delete()
                    .eq("project_id", item["project_id"])
                    .eq("report_month", item["report_month"])
                    .execute()
                )

            # Restore rows that existed before approval.
            for item in backup_rows:
                if (
                    item.get("row_existed")
                    and item.get("previous_row")
                ):
                    (
                        supabase
                        .table("project_months")
                        .insert(item["previous_row"])
                        .execute()
                    )

        except Exception as rollback_error:
            print("\n========== ROLLBACK FAILURE ==========")
            print(str(rollback_error))
            traceback.print_exc()
            print("=======================================\n")

        # Return ingestion to DRAFT.
        try:
            (
                supabase
                .table("ingestion_runs")
                .update({
                    "status": "DRAFT",
                    "approved_at": None,
                    "notes": (
                        "Agent 2 failed. Production records "
                        "were rolled back where possible. "
                        f"Error: {error_message}"
                    ),
                })
                .eq("id", ingestion_run_id)
                .execute()
            )
        except Exception as state_error:
            print(
                "Failed to reset ingestion state:",
                str(state_error),
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "Agent 2 failed. Draft remains unapproved: "
                f"{error_message}"
            ),
        )
@app.get("/agent/risk")
def get_agent_risk():
    try:
        # Latest allowed reporting month
        latest = (
            supabase.table("project_risk")
            .select("report_month")
            .gte("report_month", "2023-01-01")
            .lte("report_month", "2024-12-01")
            .order("report_month", desc=True)
            .limit(1)
            .execute()
        )

        if not latest.data:
            raise HTTPException(
                status_code=404,
                detail="No risk data found for 2023-2024"
            )

        report_month = latest.data[0]["report_month"]

        # Fetch risk predictions
        all_rows = []
        batch_size = 500

        for start in range(0, 10000, batch_size):
            result = (
                supabase.table("project_risk")
                .select("*")
                .eq("report_month", report_month)
                .range(start, start + batch_size - 1)
                .execute()
            )

            rows = result.data or []
            all_rows.extend(rows)

            if len(rows) < batch_size:
                break

        # Get project metadata
        project_ids = list({
            row["project_id"]
            for row in all_rows
            if row.get("project_id")
        })

        projects_map = {}

        for start in range(0, len(project_ids), 500):
            batch_ids = project_ids[start:start + 500]

            result = (
                supabase.table("projects")
                .select("project_id,project_name,agency,state")
                .in_("project_id", batch_ids)
                .execute()
            )

            for project in result.data or []:
                projects_map[project["project_id"]] = project

        # Merge metadata + risk prediction
        enriched_rows = []

        for row in all_rows:
            project = projects_map.get(row["project_id"], {})

            enriched_rows.append({
                **row,
                "project_name": project.get("project_name"),
                "agency": project.get("agency"),
                "state": project.get("state"),
            })

        return {
            "report_month": report_month,
            "total": len(enriched_rows),
            "data": enriched_rows
        }

    except HTTPException:
        raise

    except Exception as e:
        print("Agent risk error:", str(e))
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@app.get("/agent/risk/summary")
def get_risk_summary():
    try:
        # Find latest reporting month within allowed period
        latest = (
            supabase.table("project_risk")
            .select("report_month")
            .gte("report_month", "2023-01-01")
            .lte("report_month", "2024-12-01")
            .order("report_month", desc=True)
            .limit(1)
            .execute()
        )

        if not latest.data:
            raise HTTPException(
                status_code=404,
                detail="No risk data found for 2023-2024"
            )

        report_month = latest.data[0]["report_month"]

        # Fetch ALL records using pagination
        all_rows = []
        batch_size = 500

        for start in range(0, 10000, batch_size):
            result = (
                supabase.table("project_risk")
                .select("risk_level")
                .eq("report_month", report_month)
                .range(start, start + batch_size - 1)
                .execute()
            )

            rows = result.data or []
            all_rows.extend(rows)

            if len(rows) < batch_size:
                break

        # Calculate summary
        total = len(all_rows)

        high = sum(
            1 for row in all_rows
            if str(row.get("risk_level", "")).lower() == "high"
        )

        medium = sum(
            1 for row in all_rows
            if str(row.get("risk_level", "")).lower() == "medium"
        )

        low = sum(
            1 for row in all_rows
            if str(row.get("risk_level", "")).lower() == "low"
        )

        return {
            "report_month": report_month,
            "total": total,
            "high": high,
            "medium": medium,
            "low": low
        }

    except HTTPException:
        raise

    except Exception as e:
        print("Risk summary error:", str(e))
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# AGENT 3 & AGENT 4 ENDPOINTS
# ============================================================

@app.get("/agent/changes/{project_id}")
def get_project_changes(project_id: str):
    """
    Agent 3:
    Detect and surface changes between reporting periods for a project.
    """
    try:
        history_df = build_project_history(project_id)

        if history_df.empty:
            raise HTTPException(
                status_code=404,
                detail="Project not found.",
            )

        history = [
            predict_row(row)
            for _, row in history_df.iterrows()
        ]

        agent3 = Agent3UpdateAgent()
        result = agent3.compute_project_changes(
            project_id=project_id,
            history_records=history,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Agent 3 error for project {project_id}:", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Agent 3 change detection failed: {str(e)}"
        )


@app.get("/agent/recommend/{project_id}")
def get_project_recommendations(project_id: str):
    """
    Agent 4:
    Generate actionable prescriptions based on project data, risk predictions,
    and historical changes.
    """
    try:
        history_df = build_project_history(project_id)

        if history_df.empty:
            raise HTTPException(
                status_code=404,
                detail="Project not found.",
            )

        history = [
            predict_row(row)
            for _, row in history_df.iterrows()
        ]

        latest = history[-1]

        # Check precomputed latest risk from project_risk table if available
        risk_resp = (
            supabase
            .table("project_risk")
            .select("*")
            .eq("project_id", project_id)
            .order("report_month", desc=True)
            .limit(1)
            .execute()
        )

        if risk_resp.data:
            latest_risk = risk_resp.data[0]
            latest["delay_probability"] = float(latest_risk.get("model_delay_probability") or latest.get("delay_probability") or 0)
            latest["risk_score_100"] = float(latest_risk.get("risk_score_100") or latest.get("risk_score_100") or 0)
            latest["risk_level"] = latest_risk.get("risk_level") or latest.get("risk_level")
            drivers = latest_risk.get("top_risk_drivers")
            if drivers:
                latest["top_risk_drivers"] = drivers if isinstance(drivers, list) else [drivers]

        # Get Agent 3 changes context
        agent3 = Agent3UpdateAgent()
        changes_info = agent3.compute_project_changes(
            project_id=project_id,
            history_records=history,
        )

        # Generate Agent 4 recommendations
        agent4 = Agent4PrescriptionAgent()
        recommendations = agent4.generate_recommendations(
            project=latest,
            risk_info=latest,
            changes_info=changes_info,
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        print(f"Agent 4 error for project {project_id}:", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Agent 4 recommendation failed: {str(e)}"
        )