from pathlib import Path
import json
import joblib
import pandas as pd
import numpy as np


class MLAgent:
    """
    Agent 2:
    Approved project-month data
        -> ML-ready features
        -> Random Forest prediction
    """

    def __init__(self, model_path=None, metadata_path=None):
        base_dir = Path(__file__).resolve().parent.parent

        self.model_path = Path(
            model_path or base_dir / "paimana_random_forest.joblib"
        )

        self.metadata_path = Path(
            metadata_path or base_dir / "model_metadata.json"
        )

        self.model = joblib.load(self.model_path)

        with open(self.metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    def get_features(self):
        """
        Return exactly the feature columns expected by the trained model.
        The saved sklearn pipeline is the source of truth at inference time.
        """
        if hasattr(self.model, "feature_names_in_"):
            return list(self.model.feature_names_in_)

        features = self.metadata.get("feature_columns")

        if features:
            return features

        raise ValueError(
            "Unable to determine model feature columns."
        )

    @staticmethod
    def months_between(start, end):
        if pd.isna(start) or pd.isna(end):
            return np.nan

        return (
            (end.year - start.year) * 12
            + (end.month - start.month)
        )

    @staticmethod
    def percentage_change(current, previous):
        if pd.isna(current) or pd.isna(previous):
            return np.nan

        if previous == 0:
            return np.nan

        return ((current - previous) / abs(previous)) * 100

    def build_features(self, history_df):
        """
        Convert raw project_month history into ML-ready rows.

        The dataframe must contain one or more monthly observations
        for each project.
        """

        if history_df.empty:
            raise ValueError("Project history is empty.")

        df = history_df.copy()

        df["project_id"] = df["project_id"].astype(str)

        df["report_month"] = pd.to_datetime(
            df["report_month"],
            errors="coerce",
        )

        date_columns = [
            "original_completion",
            "revised_completion",
            "anticipated_completion",
        ]

        for column in date_columns:
            if column in df.columns:
                df[column] = pd.to_datetime(
                    df[column],
                    errors="coerce",
                )

        numeric_columns = [
            "original_cost",
            "revised_cost",
            "anticipated_cost",
            "expenditure",
            "physical_progress",
            "time_overrun",
            "cost_overrun",
            "additional_delay_flag",
            "additional_delay_months",
        ]

        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        df = df.sort_values(
            ["project_id", "report_month"]
        ).reset_index(drop=True)

        # Previous observation for each project.
        df["previous_report_month"] = (
            df.groupby("project_id")["report_month"]
            .shift(1)
        )

        df["previous_anticipated_completion"] = (
            df.groupby("project_id")["anticipated_completion"]
            .shift(1)
        )

        df["previous_anticipated_cost"] = (
            df.groupby("project_id")["anticipated_cost"]
            .shift(1)
        )

        df["previous_expenditure"] = (
            df.groupby("project_id")["expenditure"]
            .shift(1)
        )

        df["previous_physical_progress"] = (
            df.groupby("project_id")["physical_progress"]
            .shift(1)
        )

        # Observation counters.
        df["project_observation_number"] = (
            df.groupby("project_id").cumcount() + 1
        )

        df["prior_report_count"] = (
            df["project_observation_number"] - 1
        )

        # Months since previous report.
        df["months_since_previous_report"] = df.apply(
            lambda row: self.months_between(
                row["previous_report_month"],
                row["report_month"],
            ),
            axis=1,
        )

        # Schedule movement since previous report.
        df["schedule_shift_since_previous_month"] = df.apply(
            lambda row: self.months_between(
                row["previous_anticipated_completion"],
                row["anticipated_completion"],
            ),
            axis=1,
        )

        # Cost movement.
        df["anticipated_cost_change_pct"] = df.apply(
            lambda row: self.percentage_change(
                row["anticipated_cost"],
                row["previous_anticipated_cost"],
            ),
            axis=1,
        )

        # Expenditure movement.
        df["expenditure_change"] = (
            df["expenditure"]
            - df["previous_expenditure"]
        )

        # Physical progress movement.
        df["physical_progress_change"] = (
            df["physical_progress"]
            - df["previous_physical_progress"]
        )

        # Months remaining to anticipated completion.
        df["months_to_anticipated_completion"] = df.apply(
            lambda row: self.months_between(
                row["report_month"],
                row["anticipated_completion"],
            ),
            axis=1,
        )

        # Original schedule slippage.
        df["months_original_schedule_slippage"] = df.apply(
            lambda row: self.months_between(
                row["original_completion"],
                row["anticipated_completion"],
            ),
            axis=1,
        )

        # Current cost overrun percentage.
        df["current_cost_overrun_pct"] = df.apply(
            lambda row: (
                ((row["anticipated_cost"] - row["original_cost"])
                 / abs(row["original_cost"])) * 100
                if pd.notna(row["anticipated_cost"])
                and pd.notna(row["original_cost"])
                and row["original_cost"] != 0
                else np.nan
            ),
            axis=1,
        )

        # Expenditure compared with anticipated cost.
        df["expenditure_vs_anticipated_cost_pct"] = df.apply(
            lambda row: (
                (row["expenditure"] / row["anticipated_cost"]) * 100
                if pd.notna(row["expenditure"])
                and pd.notna(row["anticipated_cost"])
                and row["anticipated_cost"] != 0
                else np.nan
            ),
            axis=1,
        )

        # A newly uploaded current report has no next-month target yet.
        df["has_next_month_target"] = 0

        # Target-related columns must never be invented.
        df["is_derived_delay_label"] = 0
        df["target_next_month_additional_delay"] = 0
        df["target_next_month_schedule_shift_months"] = 0
        df["target_next_month_cost_change_pct"] = 0

        return df

    def prepare_features(self, df):
        """
        Prepare inference data without destroying categorical features.

        The saved sklearn pipeline performs:
          - categorical imputation + one-hot encoding
          - numeric median imputation

        Therefore this method only normalizes numeric columns and leaves
        categorical columns as object/string values.
        """
        features = self.get_features()

        missing = [
            column
            for column in features
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "ML dataset is missing required features: "
                + ", ".join(missing)
            )

        X = df[features].copy()

        categorical_columns = {
            "agency",
            "state",
            "delay_reason_category",
        }

        numeric_columns = [
            column
            for column in features
            if column not in categorical_columns
        ]

        for column in numeric_columns:
            X[column] = pd.to_numeric(
                X[column],
                errors="coerce",
            )

        for column in categorical_columns:
            if column in X.columns:
                X[column] = X[column].astype("object")

        X = X.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        # Do not fill NaNs here. The trained sklearn pipeline owns
        # the categorical and numeric imputation strategies.
        return X

    def predict(self, df):

        """
        Generate delay-risk predictions.
        """

        X = self.prepare_features(df)

        probabilities = self.model.predict_proba(X)[:, 1]

        result = df.copy()

        result["model_delay_probability"] = probabilities
        result["risk_score_100"] = probabilities * 100

        result["risk_level"] = result[
            "risk_score_100"
        ].apply(self.risk_level)

        return result

    @staticmethod
    def risk_level(score):
        if score < 30:
            return "Low"

        if score <= 60:
            return "Medium"

        return "High"

    def run_from_history(self, history_df):
        """
        Agent 2 complete workflow:

        raw monthly history
            -> ML features
            -> prediction
        """

        if history_df.empty:
            raise ValueError(
                "Project history is empty."
            )

        features = self.build_features(
            history_df
        )

        predictions = self.predict(
            features
        )

        return {
            "agent": "ML Agent",
            "status": "completed",
            "input_rows": len(history_df),
            "feature_rows": len(features),
            "predicted_rows": len(predictions),
            "high_risk": int(
                (predictions["risk_level"] == "High").sum()
            ),
            "medium_risk": int(
                (predictions["risk_level"] == "Medium").sum()
            ),
            "low_risk": int(
                (predictions["risk_level"] == "Low").sum()
            ),
            "predictions": predictions,
        }

    def run(self, csv_path, output_path=None):
        """
        Existing CSV-based Agent 2 workflow.
        """

        csv_path = Path(csv_path)

        df = pd.read_csv(csv_path)

        if df.empty:
            raise ValueError(
                "ML-ready dataset is empty."
            )

        predictions = self.predict(df)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            predictions.to_csv(
                output_path,
                index=False,
            )

        return {
            "agent": "ML Agent",
            "status": "completed",
            "input_rows": len(df),
            "predicted_rows": len(predictions),
            "high_risk": int(
                (predictions["risk_level"] == "High").sum()
            ),
            "medium_risk": int(
                (predictions["risk_level"] == "Medium").sum()
            ),
            "low_risk": int(
                (predictions["risk_level"] == "Low").sum()
            ),
            "predictions": predictions,
        }