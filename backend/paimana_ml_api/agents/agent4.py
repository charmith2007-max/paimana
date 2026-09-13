"""
PAIMANA Agent 4 — Prescription / Recommendation Agent

Responsibility:
Generate neutral, data-grounded decision-support recommendations based on
actual project parameters, ML risk estimates, and observed period changes.

Principles:
- Grounded strictly in actual numbers and observed features.
- Neutral decision-support guidance; does not invent official government policies,
  mandatory statutory directives, or unverified legal requirements.
- Fully explainable and traceable to input metrics.
"""

from typing import Any
import pandas as pd
import numpy as np


class Agent4PrescriptionAgent:
    """
    Agent 4:
    Translates actual project data + Agent 2 risk output + Agent 3 changes
    into neutral, actionable decision-support recommendations.
    """

    def __init__(self):
        pass

    @staticmethod
    def _to_num(val: Any) -> float | None:
        if val is None or pd.isna(val):
            return None
        try:
            n = float(val)
            return n if np.isfinite(n) else None
        except (ValueError, TypeError):
            return None

    def generate_recommendations(
        self,
        project: dict[str, Any],
        risk_info: dict[str, Any],
        changes_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Produce structured, neutral decision-support recommendations
        derived solely from actual project data and risk signals.
        """
        prescriptions: list[dict[str, Any]] = []

        risk_level = str(risk_info.get("risk_level") or "Low").capitalize()
        risk_score = self._to_num(risk_info.get("risk_score_100") or risk_info.get("risk_score") or 0) or 0.0
        delay_prob = self._to_num(risk_info.get("delay_probability") or risk_info.get("model_delay_probability") or 0) or 0.0
        drivers = risk_info.get("top_risk_drivers") or []
        if isinstance(drivers, str):
            drivers = [drivers]

        cost_overrun = self._to_num(project.get("cost_overrun"))
        time_overrun = self._to_num(project.get("time_overrun"))
        physical_progress = self._to_num(project.get("physical_progress"))
        original_cost = self._to_num(project.get("original_cost"))
        anticipated_cost = self._to_num(project.get("anticipated_cost"))
        expenditure = self._to_num(project.get("expenditure"))
        agency = str(project.get("agency") or "Executing Agency")

        # 1. Risk Level Decision Support
        if risk_level == "High" or risk_score >= 60:
            drivers_text = ", ".join(drivers[:2]) if drivers else "model-identified risk drivers"
            prescriptions.append({
                "id": "rx-high-risk-review",
                "priority": "High",
                "category": "Risk Review",
                "action_title": "Prioritize Project Review and Monitor Identified Risk Drivers",
                "rationale": (
                    f"Model estimates a high next-month delay probability of {delay_prob * 100:.1f}% "
                    f"(composite risk score: {risk_score:.1f}/100), primarily driven by: {drivers_text}."
                ),
                "recommended_steps": [
                    f"Conduct a dedicated review with {agency} regarding top risk drivers.",
                    "Track monthly milestone commitments to mitigate further delay accumulation.",
                    "Review critical-path dependencies to prevent downstream schedule spillover.",
                ],
            })
        elif risk_level == "Medium" or (30 <= risk_score < 60):
            prescriptions.append({
                "id": "rx-medium-risk-oversight",
                "priority": "Medium",
                "category": "Risk Review",
                "action_title": "Monitor Moderate Delay Risk and Watchlist Factors",
                "rationale": (
                    f"Project exhibits moderate risk signals (score: {risk_score:.1f}/100, "
                    f"delay probability: {delay_prob * 100:.1f}%)."
                ),
                "recommended_steps": [
                    f"Monitor monthly progress reports from {agency} for any worsening indicators.",
                    "Verify execution timelines against scheduled completion targets.",
                ],
            })

        # 2. Accumulated Time Overrun
        if time_overrun is not None and time_overrun >= 6:
            prescriptions.append({
                "id": "rx-time-overrun-milestones",
                "priority": "High" if time_overrun >= 12 else "Medium",
                "category": "Schedule",
                "action_title": f"Review Project Milestones Given {int(time_overrun)} Months Accumulated Slippage",
                "rationale": (
                    f"Project has recorded {int(time_overrun)} months of schedule slippage beyond the original timeline."
                ),
                "recommended_steps": [
                    "Review revised milestone schedules with project engineers.",
                    "Identify specific lagged activities contributing to accumulated time overrun.",
                ],
            })

        # 3. Observed Schedule Shift Between Reporting Periods
        if changes_info and changes_info.get("changes"):
            for ch in changes_info["changes"]:
                if ch.get("category") == "Schedule" and ch.get("direction") == "worsened":
                    prescriptions.append({
                        "id": "rx-period-schedule-shift",
                        "priority": "High" if "later" in str(ch.get("delta", "")) else "Medium",
                        "category": "Schedule",
                        "action_title": f"Investigate Observed Schedule Shift ({ch.get('delta')})",
                        "rationale": (
                            f"Anticipated completion moved from {ch.get('previous')} to {ch.get('current')} "
                            f"({ch.get('delta')}) between the last two reporting periods."
                        ),
                        "recommended_steps": [
                            f"Request clarification from {agency} on the factors causing the timeline extension.",
                            "Assess whether the timeline shift impacts interconnected infrastructure components.",
                        ],
                    })
                    break

        # 4. Cost Overrun & Trajectory
        if cost_overrun is not None and cost_overrun > 10:
            cost_details = ""
            if original_cost is not None and anticipated_cost is not None:
                cost_details = f" (Original: ₹{original_cost:,.2f} Cr, Anticipated: ₹{anticipated_cost:,.2f} Cr)"
            prescriptions.append({
                "id": "rx-cost-trajectory-review",
                "priority": "High" if cost_overrun > 25 else "Medium",
                "category": "Cost",
                "action_title": f"Review Cost Trajectory Given {cost_overrun:.1f}% Cost Variation",
                "rationale": (
                    f"Reported cost variation is {cost_overrun:.1f}% over the original budget{cost_details}."
                ),
                "recommended_steps": [
                    "Examine cost variation breakdown across major component heads.",
                    "Review expenditure pace against remaining anticipated commitments.",
                ],
            })

        # 5. Physical Progress Review
        if physical_progress is not None:
            if physical_progress < 50 and (time_overrun or 0) > 6:
                prescriptions.append({
                    "id": "rx-progress-bottleneck-review",
                    "priority": "Medium",
                    "category": "Progress",
                    "action_title": f"Review Physical Progress Constraints ({physical_progress:.1f}% Reported)",
                    "rationale": (
                        f"Reported physical progress stands at {physical_progress:.1f}% while {int(time_overrun or 0)} months "
                        "of time overrun have accumulated."
                    ),
                    "recommended_steps": [
                        "Review execution bottlenecks and constraints reported on the ground.",
                        "Evaluate resource mobilization levels against planned activity requirements.",
                    ],
                })
            elif physical_progress >= 90 and physical_progress < 100:
                prescriptions.append({
                    "id": "rx-completion-readiness",
                    "priority": "Low",
                    "category": "Progress",
                    "action_title": f"Track Final Completion Milestones ({physical_progress:.1f}% Progress)",
                    "rationale": (
                        f"Project is in final stages with {physical_progress:.1f}% physical progress completed."
                    ),
                    "recommended_steps": [
                        "Track remaining milestone activities required for project closure.",
                    ],
                })

        # 6. Baseline / Healthy Monitoring Fallback
        if not prescriptions:
            prescriptions.append({
                "id": "rx-routine-monitoring",
                "priority": "Low",
                "category": "Monitoring",
                "action_title": "Maintain Standard Progress Tracking",
                "rationale": (
                    "Project indicators are currently within standard ranges with no acute risk or delay flags."
                ),
                "recommended_steps": [
                    "Continue routine monthly data verification and milestone tracking.",
                ],
            })

        return {
            "project_id": str(project.get("project_id", "")),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "prescriptions_count": len(prescriptions),
            "prescriptions": prescriptions,
            "generated_at": pd.Timestamp.now(tz=None).strftime("%Y-%m-%d %H:%M:%S"),
        }

