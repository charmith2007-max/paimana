"""
PAIMANA Agent 3 — Data / Information Update Agent

Responsibility:
Track approved project data and risk information across reporting periods,
detect meaningful movements (cost growth, schedule slippage, progress changes,
and risk shifts), and surface actionable deltas to the system.
"""

from typing import Any
import pandas as pd
import numpy as np


class Agent3UpdateAgent:
    """
    Agent 3:
    Detects and surfaces changes between reporting periods from approved project data.
    Does not run ML models; computes deterministic deltas and risk shifts.
    """

    def __init__(self):
        pass

    @staticmethod
    def _parse_date(val: Any) -> pd.Timestamp | None:
        if val is None or pd.isna(val) or val == "":
            return None
        try:
            ts = pd.to_datetime(val, errors="coerce")
            return ts if pd.notna(ts) else None
        except Exception:
            return None

    @staticmethod
    def _to_num(val: Any) -> float | None:
        if val is None or pd.isna(val):
            return None
        try:
            n = float(val)
            return n if np.isfinite(n) else None
        except (ValueError, TypeError):
            return None

    def compute_project_changes(
        self,
        project_id: str,
        history_records: list[dict],
    ) -> dict[str, Any]:
        """
        Compare the latest monthly report with the preceding monthly report
        for the given project to compute all meaningful deltas.
        """
        if not history_records or len(history_records) < 1:
            return {
                "project_id": project_id,
                "has_previous_period": False,
                "current_month": None,
                "previous_month": None,
                "changes": [],
                "summary": "No historical observations available.",
                "risk_movement": "unchanged",
            }

        # Sort chronologically
        sorted_records = sorted(
            history_records,
            key=lambda r: str(r.get("report_month") or "")
        )

        current = sorted_records[-1]
        current_month = str(current.get("report_month") or "")

        if len(sorted_records) == 1:
            return {
                "project_id": project_id,
                "has_previous_period": False,
                "current_month": current_month,
                "previous_month": None,
                "changes": [],
                "summary": f"Initial observation for {current_month}. No prior reporting period to compare.",
                "risk_movement": "baseline",
            }

        prev = sorted_records[-2]
        prev_month = str(prev.get("report_month") or "")

        source_rep = current.get("source_report")
        source_pg = current.get("source_page")

        changes: list[dict[str, Any]] = []

        # 1. Schedule Shift
        curr_antic_comp = self._parse_date(current.get("anticipated_completion"))
        prev_antic_comp = self._parse_date(prev.get("anticipated_completion"))

        if curr_antic_comp and prev_antic_comp:
            months_shift = (curr_antic_comp.year - prev_antic_comp.year) * 12 + (
                curr_antic_comp.month - prev_antic_comp.month
            )
            if months_shift != 0:
                direction = "worsened" if months_shift > 0 else "improved"
                severity = "High" if months_shift > 3 else ("Medium" if months_shift > 0 else "Low")
                changes.append({
                    "category": "Schedule",
                    "metric": "Anticipated Completion",
                    "previous": prev_antic_comp.strftime("%b %Y"),
                    "current": curr_antic_comp.strftime("%b %Y"),
                    "delta": f"{abs(months_shift)} month{'s' if abs(months_shift) != 1 else ''} {'later' if months_shift > 0 else 'earlier'}",
                    "direction": direction,
                    "severity": severity,
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # 2. Time Overrun Delta
        curr_time_or = self._to_num(current.get("time_overrun"))
        prev_time_or = self._to_num(prev.get("time_overrun"))
        if curr_time_or is not None and prev_time_or is not None:
            time_diff = curr_time_or - prev_time_or
            if abs(time_diff) >= 1:
                changes.append({
                    "category": "Schedule",
                    "metric": "Reported Time Overrun",
                    "previous": f"{int(prev_time_or)} mo",
                    "current": f"{int(curr_time_or)} mo",
                    "delta": f"{'+' if time_diff > 0 else ''}{int(time_diff)} mo",
                    "direction": "worsened" if time_diff > 0 else "improved",
                    "severity": "Medium" if time_diff > 0 else "Low",
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # 3. Anticipated Cost Movement
        curr_cost = self._to_num(current.get("anticipated_cost"))
        prev_cost = self._to_num(prev.get("anticipated_cost"))
        if curr_cost is not None and prev_cost is not None:
            cost_diff = curr_cost - prev_cost
            if abs(cost_diff) > 0.01:
                pct = (cost_diff / abs(prev_cost) * 100) if prev_cost != 0 else 0
                direction = "worsened" if cost_diff > 0 else "improved"
                severity = "High" if pct > 5 else ("Medium" if cost_diff > 0 else "Low")
                changes.append({
                    "category": "Cost",
                    "metric": "Anticipated Cost",
                    "previous": f"₹{prev_cost:,.2f} Cr",
                    "current": f"₹{curr_cost:,.2f} Cr",
                    "delta": f"{'+' if cost_diff > 0 else ''}₹{cost_diff:,.2f} Cr ({pct:+.1f}%)",
                    "direction": direction,
                    "severity": severity,
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # 4. Expenditure Delta
        curr_exp = self._to_num(current.get("expenditure"))
        prev_exp = self._to_num(prev.get("expenditure"))
        if curr_exp is not None and prev_exp is not None:
            exp_diff = curr_exp - prev_exp
            if abs(exp_diff) > 0.01:
                changes.append({
                    "category": "Financial",
                    "metric": "Cumulative Expenditure",
                    "previous": f"₹{prev_exp:,.2f} Cr",
                    "current": f"₹{curr_exp:,.2f} Cr",
                    "delta": f"+₹{exp_diff:,.2f} Cr" if exp_diff > 0 else f"-₹{abs(exp_diff):,.2f} Cr",
                    "direction": "neutral",
                    "severity": "Low",
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # 5. Physical Progress Movement
        curr_prog = self._to_num(current.get("physical_progress"))
        prev_prog = self._to_num(prev.get("physical_progress"))
        if curr_prog is not None and prev_prog is not None:
            prog_diff = curr_prog - prev_prog
            if abs(prog_diff) > 0.01:
                direction = "improved" if prog_diff > 0 else "worsened"
                severity = "Medium" if prog_diff < 0 else "Low"
                changes.append({
                    "category": "Progress",
                    "metric": "Physical Progress",
                    "previous": f"{prev_prog:.1f}%",
                    "current": f"{curr_prog:.1f}%",
                    "delta": f"{prog_diff:+.1f}%",
                    "direction": direction,
                    "severity": severity,
                    "source_report": source_rep,
                    "source_page": source_pg,
                })
            elif curr_prog < 100:
                # Progress stalled
                changes.append({
                    "category": "Progress",
                    "metric": "Physical Progress",
                    "previous": f"{prev_prog:.1f}%",
                    "current": f"{curr_prog:.1f}%",
                    "delta": "0.0% (Stalled)",
                    "direction": "worsened",
                    "severity": "Medium",
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # 6. Risk Score & Level Shift
        curr_score = self._to_num(current.get("risk_score_100") or current.get("risk_score"))
        prev_score = self._to_num(prev.get("risk_score_100") or prev.get("risk_score"))
        curr_level = str(current.get("risk_level") or "Low")
        prev_level = str(prev.get("risk_level") or "Low")

        risk_movement = "unchanged"
        if curr_score is not None and prev_score is not None:
            score_diff = curr_score - prev_score
            if abs(score_diff) >= 0.5 or curr_level != prev_level:
                if score_diff > 0:
                    risk_movement = "increased"
                    direction = "worsened"
                    severity = "High" if score_diff > 10 or curr_level == "High" else "Medium"
                else:
                    risk_movement = "decreased"
                    direction = "improved"
                    severity = "Low"

                changes.append({
                    "category": "Risk Intelligence",
                    "metric": "Composite Risk Score",
                    "previous": f"{prev_score:.1f} ({prev_level})",
                    "current": f"{curr_score:.1f} ({curr_level})",
                    "delta": f"{score_diff:+.1f} pts ({prev_level} → {curr_level})",
                    "direction": direction,
                    "severity": severity,
                    "source_report": source_rep,
                    "source_page": source_pg,
                })

        # Build human-readable summary
        notable_worsened = [c for c in changes if c["direction"] == "worsened"]
        notable_improved = [c for c in changes if c["direction"] == "improved"]

        if notable_worsened:
            summary = f"Detected {len(notable_worsened)} adverse change(s) since {prev_month}, including {notable_worsened[0]['metric'].lower()} ({notable_worsened[0]['delta']})."
        elif notable_improved:
            summary = f"Project showed progress since {prev_month} with improvements in {notable_improved[0]['metric'].lower()} ({notable_improved[0]['delta']})."
        else:
            summary = f"Project parameters remained steady between {prev_month} and {current_month}."

        return {
            "project_id": project_id,
            "has_previous_period": True,
            "current_month": current_month,
            "previous_month": prev_month,
            "changes": changes,
            "summary": summary,
            "risk_movement": risk_movement,
        }
