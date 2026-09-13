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

        Recognizes project tables dynamically across all MoSPI Flash Report formats:
        - Format A: Dedicated PROJECT ID, PROJECT NAME, COST, EXPENDITURE, PROGRESS columns.
        - Format B / Standard: Ongoing project tables with embedded (Agency) (Project Code),
          state carry-forward, multi-value date/cost columns, and sector categorization.

        Sector/category summary tables (e.g. Project Counts by Sector) are explicitly skipped.
        """

        INDIAN_STATES = [
            "ANDAMAN AND NICOBAR ISLANDS", "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM",
            "BIHAR", "CHANDIGARH", "CHHATTISGARH", "DADRA AND NAGAR HAVELI", "DAMAN AND DIU",
            "DELHI", "GOA", "GUJARAT", "HARYANA", "HIMACHAL PRADESH", "JAMMU AND KASHMIR",
            "JHARKHAND", "KARNATAKA", "KERALA", "LADAKH", "LAKSHADWEEP", "MADHYA PRADESH",
            "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "ODISHA",
            "PUDUCHERRY", "PUNJAB", "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA",
            "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL", "MULTI STATE", "MULTI-STATE"
        ]

        rows = []
        current_state = ""
        current_sector = ""

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

        def parse_dates_from_cell(value):
            text = clean(value)
            if not text or text.upper() in {"-", "N.A.", "NA", "N/A"}:
                return None, None, None

            ant_match = re.search(r"\{(\d{1,2})[/-](\d{4})\}", text)
            rev_match = re.search(r"\(([A-Za-z]{3}|\d{1,2})[/-](\d{2,4})\)", text)
            all_dates = re.findall(r"\b(0?[1-9]|1[0-2])[/-](20\d{2})\b", text)

            orig_date = None
            if all_dates:
                orig_date = f"{int(all_dates[0][1]):04d}-{int(all_dates[0][0]):02d}-01"

            ant_date = None
            if ant_match:
                ant_date = f"{int(ant_match.group(2)):04d}-{int(ant_match.group(1)):02d}-01"
            elif len(all_dates) >= 2:
                ant_date = f"{int(all_dates[-1][1]):04d}-{int(all_dates[-1][0]):02d}-01"

            rev_date = None
            if rev_match:
                try:
                    m_str, y_str = rev_match.group(1), rev_match.group(2)
                    if len(y_str) == 2:
                        y_str = f"20{y_str}"
                    if m_str.isdigit():
                        rev_date = f"{int(y_str):04d}-{int(m_str):02d}-01"
                    else:
                        dt = pd.to_datetime(f"{m_str}-{y_str}", format="%b-%Y", errors="coerce")
                        if pd.notna(dt):
                            rev_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            return orig_date, rev_date, ant_date

        def parse_costs_from_cell(value):
            text = clean(value).replace(",", "")
            if not text or text.upper() in {"-", "N.A.", "NA", "N/A"}:
                return None, None, None

            ant_match = re.search(r"\{([\d.]+)\}", text)
            rev_match = re.search(r"\(([\d.]+)\)", text)
            numbers = re.findall(r"-?\d+(?:\.\d+)?", text)

            orig_cost = float(numbers[0]) if numbers else None
            rev_cost = float(rev_match.group(1)) if rev_match else None
            ant_cost = float(ant_match.group(1)) if ant_match else None

            if ant_cost is None:
                if len(numbers) >= 3:
                    ant_cost = float(numbers[2])
                elif len(numbers) >= 2:
                    ant_cost = float(numbers[1])
                else:
                    ant_cost = orig_cost

            if rev_cost is None and len(numbers) >= 2:
                rev_cost = float(numbers[1])

            return orig_cost, rev_cost, ant_cost

        def parse_project_block(cell):
            text = clean(cell)
            code_matches = re.findall(r"\(([A-Za-z]?\d{6,9})\)", str(cell))
            if not code_matches:
                code_matches = re.findall(r"\b([A-Za-z]\d{8,9})\b", str(cell))
            if not code_matches:
                code_matches = re.findall(r"\b(\d{8,9})\b", str(cell))

            if not code_matches:
                return None, None, None, None

            project_id = code_matches[0]

            state_in_cell = None
            for st in INDIAN_STATES:
                if f"({st})" in str(cell).upper():
                    state_in_cell = st
                    break

            agency_matches = re.findall(r"\(([A-Za-z\s/&-]{2,25})\)", str(cell))
            agency = None
            for a in agency_matches:
                a_clean = a.strip()
                if (
                    a_clean.upper() not in {"N.A.", "NA"}
                    and not re.match(r"^[A-Za-z]?\d+$", a_clean)
                    and a_clean.upper() not in INDIAN_STATES
                ):
                    agency = a_clean
                    break

            lines = [clean(x) for x in str(cell).split("\n") if clean(x)]
            name_lines = []
            for l in lines:
                if not re.fullmatch(r"\(.*?\)", l) and project_id not in l:
                    cleaned_line = l
                    for st in INDIAN_STATES:
                        cleaned_line = re.sub(rf"\({st}\)", "", cleaned_line, flags=re.IGNORECASE).strip()
                    if cleaned_line:
                        name_lines.append(cleaned_line)

            project_name = " ".join(name_lines).strip()
            if not project_name and lines:
                project_name = lines[0]

            return project_id, project_name, agency, state_in_cell

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_cells = [clean(x).lower() for x in table[0]]
                    header_str = " | ".join(header_cells)

                    # Skip sector/state macro summary tables
                    if "sector name" in header_str and "project count" in header_str:
                        continue
                    if header_str.startswith("sl. no. | sector | projects") or header_str.startswith("sl. no. | state | projects"):
                        continue

                    has_proj = any(k in header_str for k in ["project id", "project name", "project code", "project"])
                    has_metric = any(k in header_str for k in ["cost", "expenditure", "progress", "commissioning", "approval"])

                    if not (has_proj and has_metric):
                        continue

                    # Dynamic header-to-column index mapping
                    col_map = {}
                    for idx, h in enumerate(header_cells):
                        if "project id" in h:
                            col_map["project_id"] = idx
                        elif "project name" in h or "project" in h:
                            col_map["project_cell"] = idx
                        if "state" in h:
                            col_map["state"] = idx
                        if "sector" in h:
                            col_map["sector"] = idx
                        if "sl" in h or "s.no" in h or "sno" in h:
                            col_map["sno"] = idx
                        if "approval" in h:
                            col_map["approval"] = idx
                        if "commissioning" in h or "completion" in h or "doc" in h:
                            col_map["doc"] = idx
                        if "cost" in h and "revised" not in h and "cumulative" not in h:
                            col_map["cost"] = idx
                        if "revised cost" in h:
                            col_map["revised_cost"] = idx
                        if "original cost" in h:
                            col_map["original_cost"] = idx
                        if "expenditure" in h:
                            col_map["expenditure"] = idx
                        if "progress" in h:
                            col_map["progress"] = idx

                    for row in table[1:]:
                        if not row or len(row) < 3:
                            continue

                        # Update state from cell if present
                        if "state" in col_map and row[col_map["state"]]:
                            st_val = clean(row[col_map["state"]]).upper()
                            for st in INDIAN_STATES:
                                if st in st_val:
                                    current_state = st
                                    break

                        # Update sector from cell if present
                        if "sector" in col_map and row[col_map["sector"]]:
                            sec_val = clean(row[col_map["sector"]])
                            if sec_val and not re.match(r"^\d+$", sec_val):
                                current_sector = sec_val

                        # Extract project ID and name
                        project_id = None
                        project_name = ""
                        agency = None
                        state_in_cell = None

                        if "project_id" in col_map and row[col_map["project_id"]]:
                            pid = clean(row[col_map["project_id"]])
                            if re.fullmatch(r"[A-Za-z]?\d{6,9}", pid):
                                project_id = pid
                                if "project_cell" in col_map:
                                    project_name = clean(row[col_map["project_cell"]])

                        if not project_id and "project_cell" in col_map:
                            pid, pname, ag, st_cell = parse_project_block(row[col_map["project_cell"]])
                            if pid:
                                project_id = pid
                                project_name = pname
                                agency = ag
                                state_in_cell = st_cell

                        if not project_id or not project_name:
                            continue

                        # Determine State
                        state = state_in_cell or current_state
                        if not state:
                            state = "CENTRAL / MULTI-STATE"

                        # Determine Agency
                        if not agency:
                            agency = current_sector or "Central Sector"

                        # Costs
                        original_cost = None
                        revised_cost = None
                        anticipated_cost = None

                        if "original_cost" in col_map and row[col_map["original_cost"]]:
                            original_cost = parse_number(row[col_map["original_cost"]])
                        if "revised_cost" in col_map and row[col_map["revised_cost"]]:
                            revised_cost = parse_number(row[col_map["revised_cost"]])
                            anticipated_cost = revised_cost
                        if "cost" in col_map and row[col_map["cost"]]:
                            oc, rc, ac = parse_costs_from_cell(row[col_map["cost"]])
                            if original_cost is None:
                                original_cost = oc
                            if revised_cost is None:
                                revised_cost = rc
                            if anticipated_cost is None:
                                anticipated_cost = ac

                        if anticipated_cost is None:
                            anticipated_cost = revised_cost or original_cost

                        # Expenditure
                        expenditure = None
                        if "expenditure" in col_map and row[col_map["expenditure"]]:
                            expenditure = parse_number(row[col_map["expenditure"]])

                        # Physical Progress
                        physical_progress = None
                        if "progress" in col_map and row[col_map["progress"]]:
                            physical_progress = parse_number(row[col_map["progress"]])

                        # Dates
                        original_completion = None
                        revised_completion = None
                        anticipated_completion = None
                        if "doc" in col_map and row[col_map["doc"]]:
                            oc_d, rc_d, ac_d = parse_dates_from_cell(row[col_map["doc"]])
                            original_completion = oc_d
                            revised_completion = rc_d
                            anticipated_completion = ac_d or revised_completion or original_completion

                        is_delayed = None
                        if original_completion and anticipated_completion:
                            is_delayed = int(anticipated_completion > original_completion)

                        cost_overrun = None
                        if original_cost and original_cost > 0 and anticipated_cost is not None:
                            cost_overrun = round(((anticipated_cost - original_cost) / original_cost) * 100, 2)

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

