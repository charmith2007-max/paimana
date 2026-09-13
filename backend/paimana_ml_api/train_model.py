from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier

BASE = Path(__file__).resolve().parent
ML_FILE = BASE / "PAIMANA_ML_READY_v1.xlsx"
MODEL_FILE = BASE / "paimana_random_forest.joblib"
META_FILE = BASE / "model_metadata.json"

CATEGORICAL = ["agency", "state", "delay_reason_category"]
NUMERIC = [
    "original_cost", "revised_cost", "anticipated_cost", "expenditure",
    "physical_progress", "time_overrun", "cost_overrun", "is_delayed",
    "additional_delay_flag", "additional_delay_months", "is_derived_delay_label",
    "months_since_previous_report", "schedule_shift_since_previous_month",
    "anticipated_cost_change_pct", "expenditure_change", "physical_progress_change",
    "months_to_anticipated_completion", "months_original_schedule_slippage",
    "current_cost_overrun_pct", "expenditure_vs_anticipated_cost_pct",
    "project_observation_number", "prior_report_count"
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "target_next_month_additional_delay"

print(f"scikit-learn version: {sklearn.__version__}")
if sklearn.__version__ != "1.9.0":
    raise RuntimeError("This retraining script must run with scikit-learn 1.9.0")

if not ML_FILE.exists():
    raise FileNotFoundError(ML_FILE)

df = pd.read_excel(ML_FILE, sheet_name="ML_Features")
# Use only rows with a valid next-month target and the predefined chronological split.
train = df[(df["recommended_split"] == "train") & df[TARGET].notna()].copy()
val = df[(df["recommended_split"] == "validation") & df[TARGET].notna()].copy()
test = df[(df["recommended_split"] == "test") & df[TARGET].notna()].copy()

X_train, y_train = train[FEATURES], train[TARGET].astype(int)
X_val, y_val = val[FEATURES], val[TARGET].astype(int)
X_test, y_test = test[FEATURES], test[TARGET].astype(int)

preprocessor = ColumnTransformer([
    ("cat", Pipeline([
        ("imp", SimpleImputer(strategy="most_frequent")),
        ("oh", OneHotEncoder(handle_unknown="ignore"))
    ]), CATEGORICAL),
    ("num", SimpleImputer(strategy="median"), NUMERIC),
])

model = Pipeline([
    ("prep", preprocessor),
    ("model", RandomForestClassifier(
        n_estimators=250,
        min_samples_leaf=3,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    ))
])

model.fit(X_train, y_train)

val_p = model.predict_proba(X_val)[:, 1]
test_p = model.predict_proba(X_test)[:, 1]
metrics = {
    "validation": {
        "n": int(len(val)),
        "roc_auc": float(roc_auc_score(y_val, val_p)),
        "pr_auc": float(average_precision_score(y_val, val_p)),
    },
    "test": {
        "n": int(len(test)),
        "roc_auc": float(roc_auc_score(y_test, test_p)),
        "pr_auc": float(average_precision_score(y_test, test_p)),
    }
}

joblib.dump(model, MODEL_FILE)
metadata = {
    "features": FEATURES,
    "categorical_features": CATEGORICAL,
    "numeric_features": NUMERIC,
    "target": TARGET,
    "model": "RandomForestClassifier(n_estimators=250,min_samples_leaf=3,class_weight='balanced_subsample',random_state=42)",
    "sklearn_version": sklearn.__version__,
    "metrics": metrics,
    "risk_thresholds": {"low_lt": 30, "medium_lte": 60, "high_gt": 60},
    "training_scope": "Reports through Sep 2024",
    "validation_scope": "Oct 2024 predicting Nov 2024",
    "test_scope": "Nov 2024 predicting Dec 2024",
}
META_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(json.dumps({"model_file": str(MODEL_FILE), "metadata_file": str(META_FILE), "metrics": metrics}, indent=2))
