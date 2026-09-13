from pathlib import Path
import re
import pandas as pd
import pdfplumber


CANONICAL_COLUMNS = [
    "project_id",
    "project_name",
    "agency",
    "state",
    "report_month",
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
    "source_report",
    "source_page",
]


class IngestionAgent:
    """
    Agent 1:
    Flash Report PDF -> validated ML-ready dataset.

    The agent performs deterministic extraction and validation.
    It does not make financial or ML decisions.
    """

    def __init__(self):
        self.accepted_rows = []
        self.quarantined_rows = []
        self.warnings = []

    def detect_report_month(self, filename: str, pdf_path=None) -> str:
        """
        Detect YYYY-MM from the report.

        Detection order:
          1. Filename (full month name or abbreviation).
          2. PDF text content (first 5 pages) if filename fails.

        Raises ValueError if detection fails from both sources so the
        caller can prompt the officer for a manual month override.
        """

        name = Path(filename).stem.lower()

        # Full names AND standard abbreviations supported.
        months = {
            "january": "01",  "jan": "01",
            "february": "02", "feb": "02",
            "march": "03",    "mar": "03",
            "april": "04",    "apr": "04",
            "may": "05",
            "june": "06",     "jun": "06",
            "july": "07",     "jul": "07",
            "august": "08",   "aug": "08",
            "september": "09","sep": "09", "sept": "09",
            "october": "10",  "oct": "10",
            "november": "11", "nov": "11",
            "december": "12", "dec": "12",
        }

        year_match = re.search(r"(20\d{2})", name)
        year_from_filename = year_match.group(1) if year_match else None

        if year_from_filename:
            # Sort by length descending so "september" matches before "sep".
            for month_name in sorted(months.keys(), key=len, reverse=True):
                if month_name in name:
                    return f"{year_from_filename}-{months[month_name]}"

        # --- PDF content fallback ---
        if pdf_path is not None:
            detected = self._detect_month_from_content(pdf_path, months)
            if detected:
                return detected

        raise ValueError(
            "Could not detect report month from the filename or PDF content. "
            "Please use the 'Report Period' field to enter the month manually (YYYY-MM)."
        )

    def _detect_month_from_content(self, pdf_path, months: dict) -> str | None:
        """
        Scan the first 5 pages of the PDF for a month+year pattern.
        Returns YYYY-MM or None if not found.
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:5]:
                    text = (page.extract_text() or "").lower()

                    # Look for "Month YYYY" or "Month, YYYY"
                    year_match = re.search(r"(20\d{2})", text)
                    if not year_match:
                        continue

                    year = year_match.group(1)

                    for month_name in sorted(months.keys(), key=len, reverse=True):
                        if month_name in text:
                            return f"{year}-{months[month_name]}"
        except Exception:
            pass

        return None

    def extract_project_id(self, text: str):
        """
        Preserve the original project ID exactly.
        Supports IDs with or without N prefix.
        """

        if not text:
            return None

        patterns = [
            r"\bN\d{8}\b",
            r"\bN\d{9}\b",
            r"\b\d{9}\b",
            r"\b\d{8}\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, str(text), re.IGNORECASE)
            if match:
                return match.group(0)

        return None

    def clean_number(self, value):
        if value is None:
            return None

        value = str(value).strip()

        if not value or value.upper() in {"N.A.", "NA", "N/A", "-"}:
            return None

        value = value.replace(",", "")
        value = value.replace("₹", "")
        value = value.strip()

        try:
            return float(value)
        except ValueError:
            return None

    def clean_date(self, value):
        if value is None:
            return None

        value = str(value).strip()

        if not value or value.upper() in {"N.A.", "NA", "N/A", "-"}:
            return None

        # MM/YYYY
        match = re.fullmatch(r"(\d{1,2})/(\d{4})", value)
        if match:
            month, year = match.groups()
            return f"{year}-{int(month):02d}-01"

        # Month-YY
        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass

        return None

    def validate_row(self, row):
        errors = []

        if not row.get("project_id"):
            errors.append("Missing project ID")

        if not row.get("project_name"):
            errors.append("Missing project name")

        if not row.get("agency"):
            errors.append("Missing agency")

        if not row.get("state"):
            errors.append("Missing state")

        if not row.get("report_month"):
            errors.append("Missing report month")

        return errors

    def validate_duplicates(self, rows):
        seen = set()

        valid = []

        for row in rows:
            key = (
                row.get("project_id"),
                row.get("report_month"),
            )

            if key in seen:
                self.quarantined_rows.append({
                    **row,
                    "_quarantine_reason": "Duplicate project-month",
                })
                continue

            seen.add(key)
            valid.append(row)

        return valid

    def process_rows(self, rows):
        """
        Validate and normalize extracted rows.
        """

        self.accepted_rows = []
        self.quarantined_rows = []

        for row in rows:

            # Guarantee canonical schema
            normalized = {
                column: row.get(column)
                for column in CANONICAL_COLUMNS
            }

            # Normalize numeric fields
            for column in [
                "original_cost",
                "revised_cost",
                "anticipated_cost",
                "expenditure",
                "physical_progress",
                "time_overrun",
                "cost_overrun",
                "additional_delay_months",
            ]:
                normalized[column] = self.clean_number(
                    normalized[column]
                )

            # Normalize dates
            for column in [
                "original_completion",
                "revised_completion",
                "anticipated_completion",
            ]:
                normalized[column] = self.clean_date(
                    normalized[column]
                )

            errors = self.validate_row(normalized)

            if errors:
                self.quarantined_rows.append({
                    **normalized,
                    "_quarantine_reason": "; ".join(errors),
                })
            else:
                self.accepted_rows.append(normalized)

        self.accepted_rows = self.validate_duplicates(
            self.accepted_rows
        )

        return self.accepted_rows

    def build_dataset(self, rows, output_path):
        """
        Save accepted rows as ML-ready CSV.
        """

        df = pd.DataFrame(
            rows,
            columns=CANONICAL_COLUMNS,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(
            output_path,
            index=False,
        )

        return df

    def generate_report(self):
        return {
            "agent": "Ingestion Agent",
            "status": "completed",
            "accepted_rows": len(self.accepted_rows),
            "quarantined_rows": len(self.quarantined_rows),
            "warnings": self.warnings,
            "schema_columns": len(CANONICAL_COLUMNS),
        }


    def run_ingestion(rows, output_path):
        """
        Simple entry point for the backend/API.
        """

        agent = IngestionAgent()

        accepted = agent.process_rows(rows)

        dataset = agent.build_dataset(
            accepted,
            output_path,
        )

        return {
            "report": agent.generate_report(),
            "dataset": dataset,
            "quarantined": agent.quarantined_rows,
        }
    def identify_project_tables(self, pdf_path):
            """
            Discover tables that look like PAIMANA project tables.
            """

            candidates = []

            project_keywords = [
                "project name",
                "project code",
                "agency",
                "cost",
                "expenditure",
                "commissioning",
                "physical progress",
                "state",
            ]

            with pdfplumber.open(pdf_path) as pdf:

                for page_number, page in enumerate(
                    pdf.pages,
                    start=1
                ):

                    tables = page.extract_tables()

                    for table_number, table in enumerate(
                        tables,
                        start=1
                    ):

                        if not table:
                            continue

                        # Convert the table to searchable text.
                        text = " ".join(
                            str(cell or "")
                            for row in table
                            for cell in row
                        ).lower()

                        matches = [
                            keyword
                            for keyword in project_keywords
                            if keyword in text
                        ]

                        # A project table should contain
                        # several of these signals.
                        if len(matches) >= 3:
                            candidates.append({
                                "page": page_number,
                                "table": table_number,
                                "matched_keywords": matches,
                                "score": len(matches),
                            })

            candidates.sort(
                key=lambda x: x["score"],
                reverse=True
            )

            return candidates
    def extract_project_rows(self, pdf_path, report_month, source_report):
        """
        Schema-aware PAIMANA extraction.

        Recognizes only actual project tables:
        - Current summary project table with PROJECT ID as a dedicated column.
        - Detailed ongoing-project table with Project Name / Agency /
          Project Code embedded in one column.

        Sector/category summary tables are explicitly ignored.
        """

        rows = []

        def clean(value):
            if value is None:
                return ""
            return str(value).replace("\n", " ").strip()

        def parse_number(value):
            value = clean(value)
            if not value or value.upper() in {"-", "N.A.", "NA", "N/A"}:
                return None
            value = value.replace(",", "").replace("₹", "").strip()
            try:
                return float(value)
            except ValueError:
                return None

        def parse_two_dates(value):
            dates = re.findall(
                r"\b(0?[1-9]|1[0-2])/(20\d{2})\b",
                clean(value)
            )
            return [
                f"{int(year):04d}-{int(month):02d}-01"
                for month, year in dates[:2]
            ]

        def parse_project(cell):
            text = clean(cell)

            # In the detailed format, the actual project code is enclosed
            # in parentheses on its own line. Project descriptions can also
            # contain 6-digit chainage values such as 129000, so NEVER take
            # an arbitrary 6-9 digit number from the full text.
            code_matches = re.findall(
                r"\(([A-Za-z]?\d{6,9})\)",
                str(cell)
            )

            if not code_matches:
                return None, None, None

            project_id = code_matches[0]

            # Name/agency are normally on the first two non-empty lines.
            parts = [
                clean(x)
                for x in str(cell).split("\n")
                if clean(x)
            ]

            project_name = parts[0] if parts else ""
            agency = ""

            if len(parts) >= 2:
                agency = re.sub(
                    r"^\((.*)\)$",
                    r"\1",
                    parts[1]
                ).strip()

            return project_id, project_name, agency

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_cells = [clean(x).lower() for x in table[0]]
                    header = " | ".join(header_cells)

                    # --------------------------------------------------
                    # FORMAT A:
                    # S.NO | PROJECT ID | PROJECT NAME | ORIGINAL COST |
                    # REVISED COST | EXPENDITURE | PHYSICAL PROGRESS
                    #
                    # IMPORTANT:
                    # Require BOTH "project id" and "project name".
                    # This prevents sector summaries such as:
                    # S.NO | SECTOR NAME | PROJECT COUNT | ...
                    # from being extracted.
                    # --------------------------------------------------
                    current_format = (
                        len(header_cells) >= 7
                        and "project id" in header
                        and "project name" in header
                        and "original cost" in header
                        and "revised cost" in header
                        and "expenditure" in header
                        and "physical progress" in header
                    )

                    # --------------------------------------------------
                    # FORMAT B:
                    # S.NO | PROJECT NAME (Agency) (Project Code) |
                    # State | Approval | DoC | Cost | Expenditure |
                    # Physical Progress
                    # --------------------------------------------------
                    detailed_format = (
                        len(header_cells) >= 8
                        and "project name" in header
                        and "state" in header
                        and "date of approval" in header
                        and "physical progress" in header
                        and "cost" in header
                        and "expenditure" in header
                    )

                    if not (current_format or detailed_format):
                        continue

                    for row in table[1:]:
                        if not row or len(row) < 6:
                            continue

                        sno = clean(row[0])
                        if not re.fullmatch(r"\d{1,4}", sno):
                            continue

                        project_id = None
                        project_name = ""
                        agency = ""
                        state = ""

                        original_cost = None
                        revised_cost = None
                        expenditure = None
                        physical_progress = None
                        original_completion = None
                        revised_completion = None

                        if current_format:
                            if len(row) < 7:
                                continue

                            project_id = clean(row[1])

                            # Dedicated project ID must actually look like
                            # a PAIMANA project code.
                            if not re.fullmatch(
                                r"[A-Za-z]?\d{6,9}",
                                project_id
                            ):
                                continue

                            project_name = clean(row[2])
                            if not project_name:
                                continue

                            original_cost = parse_number(row[3])
                            revised_cost = parse_number(row[4])
                            expenditure = parse_number(row[5])
                            physical_progress = parse_number(row[6])

                        else:
                            project_id, project_name, agency = parse_project(
                                row[1]
                            )

                            if not project_id or not project_name:
                                continue

                            state = clean(row[2])

                            doc_dates = parse_two_dates(row[4])
                            original_completion = (
                                doc_dates[0]
                                if len(doc_dates) >= 1
                                else None
                            )
                            revised_completion = (
                                doc_dates[1]
                                if len(doc_dates) >= 2
                                else None
                            )

                            costs = re.findall(
                                r"-?\d+(?:\.\d+)?",
                                clean(row[5]).replace(",", "")
                            )

                            original_cost = (
                                float(costs[0])
                                if len(costs) >= 1
                                else None
                            )
                            revised_cost = (
                                float(costs[1])
                                if len(costs) >= 2
                                else None
                            )

                            expenditure = parse_number(row[6])

                            physical_progress = parse_number(
                                row[7]
                                if len(row) >= 8
                                else None
                            )

                        anticipated_completion = (
                            revised_completion or original_completion
                        )

                        anticipated_cost = (
                            revised_cost
                            if revised_cost is not None
                            else original_cost
                        )

                        is_delayed = None
                        if original_completion and anticipated_completion:
                            is_delayed = int(
                                anticipated_completion > original_completion
                            )

                        cost_overrun = None
                        if (
                            original_cost is not None
                            and original_cost != 0
                            and anticipated_cost is not None
                        ):
                            cost_overrun = round(
                                (
                                    (anticipated_cost - original_cost)
                                    / original_cost
                                ) * 100,
                                2
                            )

                        rows.append({
                            "project_id": project_id,
                            "project_name": project_name,
                            "agency": agency,
                            "state": state,
                            "report_month": f"{report_month}-01",
                            "original_cost": original_cost,
                            "revised_cost": revised_cost,
                            "anticipated_cost": anticipated_cost,
                            "expenditure": expenditure,
                            "original_completion": original_completion,
                            "revised_completion": revised_completion,
                            "anticipated_completion": anticipated_completion,
                            "physical_progress": physical_progress,
                            "time_overrun": None,
                            "cost_overrun": cost_overrun,
                            "delay_reason": None,
                            "is_delayed": is_delayed,
                            "additional_delay_flag": None,
                            "additional_delay_months": None,
                            "delay_reason_category": None,
                            "source_report": source_report,
                            "source_page": page_number,
                        })

        unique = {}
        for row in rows:
            key = (row["project_id"], row["report_month"])
            unique[key] = row

        return list(unique.values())

