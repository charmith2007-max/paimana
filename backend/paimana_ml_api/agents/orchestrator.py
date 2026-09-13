from pathlib import Path
import tempfile

from .ingestion_agent import IngestionAgent


class PAIMANAOrchestrator:
    """
    Controls the monthly PAIMANA agentic workflow.

    PDF
      ↓
    Ingestion Agent
      ↓
    Validation
      ↓
    ML-ready dataset

    ML prediction is intentionally kept as the next
    controlled stage rather than allowing an LLM to
    directly modify the model or database.
    """

    def __init__(self):
        self.ingestion_agent = IngestionAgent()

    def run_ingestion(self, rows, report_month, source_report):
        """
        Run the ingestion and validation stage.
        """

        # Add report metadata to every extracted row.
        enriched_rows = []

        for row in rows:
            row = dict(row)

            row["report_month"] = report_month
            row["source_report"] = source_report

            enriched_rows.append(row)

        accepted = self.ingestion_agent.process_rows(
            enriched_rows
        )

        report = self.ingestion_agent.generate_report()

        return {
            "stage": "ingestion",
            "status": "completed",
            "report_month": report_month,
            "source_report": source_report,
            "accepted_rows": accepted,
            "quarantined_rows": self.ingestion_agent.quarantined_rows,
            "summary": report,
        }