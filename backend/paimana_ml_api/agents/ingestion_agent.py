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

INDIAN_STATES = [
    "ANDAMAN AND NICOBAR ISLANDS", "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM",
    "BIHAR", "CHANDIGARH", "CHHATTISGARH", "CHHATISGARH", "DADRA AND NAGAR HAVELI", "DAMAN AND DIU",
    "DELHI", "GOA", "GUJARAT", "HARYANA", "HIMACHAL PRADESH", "JAMMU AND KASHMIR",
    "JHARKHAND", "KARNATAKA", "KERALA", "LADAKH", "LAKSHADWEEP", "MADHYA PRADESH",
    "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "ODISHA",
    "PUDUCHERRY", "PUNJAB", "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA",
    "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL", "MULTI STATE", "MULTI-STATE"
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
        Supports IDs with or without delimiters/prefixes.
        """
        if not text:
            return None

        match = re.search(r"[\[\(]([A-Za-z]?\d{6,9})[\]\)]", str(text))
        if match:
            return match.group(1)

        patterns = [
            r"\bN\d{8}\b",
            r"\bN\d{9}\b",
            r"\b\d{9}\b",
            r"\b\d{8}\b",
            r"\b[A-Za-z]\d{6,9}\b",
            r"\b\d{6,9}\b",
        ]

        for pattern in patterns:
            m = re.search(pattern, str(text), re.IGNORECASE)
            if m:
                return m.group(0)

        return None

    def clean_number(self, value):
        if value is None:
            return None

        value = str(value).strip()

        if not value or value.upper() in {"N.A.", "NA", "N/A", "-", "N.A", "NIL"}:
            return None

        value = value.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()

        try:
            return float(value)
        except ValueError:
            return None

    def clean_date(self, value):
        if value is None:
            return None

        value = str(value).strip()

        if not value or value.upper() in {"N.A.", "NA", "N/A", "-", "N.A", "NIL", "0/0", "00/0000"}:
            return None

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value

        match = re.fullmatch(r"(\d{1,2})/(\d{4})", value)
        if match:
            month, year = match.groups()
            return f"{year}-{int(month):02d}-01"

        try:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%Y-%m-%d")
        except Exception:
            pass

        return None

    def parse_dates_from_cell(self, value):
        """
        Format-agnostic date parsing from multi-value cells.
        Supports {Anticipated}, [Anticipated], (Revised), and bare Original dates.
        """
        text = str(value or "").replace("\n", " ").strip()
        if not text or text.upper() in {"-", "N.A.", "NA", "N/A", "NIL", "0/0"}:
            return None, None, None

        ant_match = re.search(r"[\{\[](\d{1,2})[/-](\d{2,4})[\}\]]", text)
        rev_match = re.search(r"\(([A-Za-z]{3}|\d{1,2})[/-](\d{2,4})\)", text)
        all_dates = re.findall(r"\b(0?[1-9]|1[0-2])[/-](20\d{2}|\d{2})\b", text)

        def normalize_date(m, y):
            y_int = int(y)
            if y_int < 100:
                y_int = 2000 + y_int
            m_int = int(m)
            return f"{y_int:04d}-{m_int:02d}-01"

        orig_date = None
        if all_dates:
            orig_date = normalize_date(all_dates[0][0], all_dates[0][1])

        ant_date = None
        if ant_match:
            ant_date = normalize_date(ant_match.group(1), ant_match.group(2))
        elif len(all_dates) >= 2:
            ant_date = normalize_date(all_dates[-1][0], all_dates[-1][1])

        rev_date = None
        if rev_match:
            try:
                m_str, y_str = rev_match.group(1), rev_match.group(2)
                y_int = int(y_str) if len(y_str) == 4 else (2000 + int(y_str))
                if m_str.isdigit():
                    rev_date = f"{y_int:04d}-{int(m_str):02d}-01"
                else:
                    dt = pd.to_datetime(f"{m_str}-{y_int}", format="%b-%Y", errors="coerce")
                    if pd.notna(dt):
                        rev_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        return orig_date, rev_date, ant_date

    def parse_costs_from_cell(self, value):
        """
        Format-agnostic cost parsing from multi-value cells.
        Supports {Anticipated}, [Anticipated], (Revised), and bare Original costs.
        """
        text = str(value or "").replace("\n", " ").replace(",", "").replace("₹", "").strip()
        if not text or text.upper() in {"-", "N.A.", "NA", "N/A", "NIL"}:
            return None, None, None

        ant_match = re.search(r"[\{\[]([\d.]+)[\}\]]", text)
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

    def parse_project_block(self, cell):
        """
        Format-agnostic project metadata parsing.
        Supports both inline comma formats:
          'NAME - [CODE],AGENCY,STATE'
        and multiline parentheses formats:
          'NAME\n(AGENCY)\n(CODE)\n(STATE)'
        """
        text = str(cell or "").strip()
        if not text:
            return None, None, None, None

        code_matches = re.findall(r"[\[\(]([A-Za-z]?\d{6,9})[\]\)]", text)
        if not code_matches:
            code_matches = re.findall(r"\b([A-Za-z]\d{8,9})\b", text)
        if not code_matches:
            code_matches = re.findall(r"\b(\d{8,9})\b", text)

        if not code_matches:
            return None, None, None, None

        project_id = code_matches[0]
        state_in_cell = None
        agency = None

        if " - [" in text or " - (" in text or (" - " in text and "," in text):
            parts = text.split(" - ")
            project_name = parts[0].replace("\n", " ").strip()
            meta_part = parts[-1]
            for item in meta_part.split(","):
                it = item.strip()
                it_clean = re.sub(r"[\[\]\(\)]", "", it).strip()
                if it_clean.upper() in INDIAN_STATES:
                    state_in_cell = it_clean.upper()
                elif not re.search(r"\d{6,9}", it_clean) and not agency and 2 <= len(it_clean) <= 30:
                    agency = it_clean
        else:
            for st in INDIAN_STATES:
                if f"({st})" in text.upper() or f"[{st}]" in text.upper():
                    state_in_cell = st
                    break

            agency_matches = re.findall(r"[\(\[]( [A-Za-z\s/&-]{2,25} )[\)\]]".replace(" ", ""), text)
            for a in agency_matches:
                a_clean = a.strip()
                if (
                    a_clean.upper() not in {"N.A.", "NA"}
                    and not re.match(r"^[A-Za-z]?\d+$", a_clean)
                    and a_clean.upper() not in INDIAN_STATES
                ):
                    agency = a_clean
                    break

            lines = [str(x or "").replace("\n", " ").strip() for x in text.split("\n") if str(x or "").strip()]
            name_lines = []
            for l in lines:
                if not re.fullmatch(r"[\(\[].*?[\)\]]", l) and project_id not in l:
                    cleaned_line = l
                    for st in INDIAN_STATES:
                        cleaned_line = re.sub(rf"[\(\[]{st}[\)\]]", "", cleaned_line, flags=re.IGNORECASE).strip()
                    if cleaned_line:
                        name_lines.append(cleaned_line)

            project_name = " ".join(name_lines).strip()
            if not project_name and lines:
                project_name = lines[0]

        return project_id, project_name, agency, state_in_cell

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
        Validate and normalize extracted rows into canonical schema.
        """
        self.accepted_rows = []
        self.quarantined_rows = []

        for row in rows:
            normalized = {
                column: row.get(column)
                for column in CANONICAL_COLUMNS
            }

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

    def run_ingestion(self, rows, output_path):
        """
        Simple entry point for the backend/API.
        """
        accepted = self.process_rows(rows)

        dataset = self.build_dataset(
            accepted,
            output_path,
        )

        return {
            "report": self.generate_report(),
            "dataset": dataset,
            "quarantined": self.quarantined_rows,
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
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                for table_number, table in enumerate(tables, start=1):
                    if not table:
                        continue

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
        Format-agnostic PAIMANA semantic extraction.

        Discovers project tables dynamically across all MoSPI Flash Report formats:
        - Scored Semantic Header Discovery: Discovers table column roles and preserves
          active column mappings across unrepeated continuation pages.
        - Unified Entity Parsing: Normalizes project ID, agency, state from multi-style notations.
        - Metric & Date Normalization: Handles {Anticipated}, [Anticipated], (Revised), and bare tokens.
        - Canonical Assembly: Assembles strictly typed canonical schema matching CANONICAL_COLUMNS.
        """
        rows = []
        current_state = ""
        current_sector = ""
        active_col_map = None

        def clean(value):
            if value is None:
                return ""
            return str(value).replace("\n", " ").strip()

        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 1:
                        continue

                    best_header_row_idx = None
                    best_header_col_map = None
                    best_score = 0

                    for r_idx in range(min(3, len(table))):
                        row_cells = [clean(x).lower() for x in table[r_idx]]
                        hdr_str = " | ".join(row_cells)

                        if "sector name" in hdr_str and "project count" in hdr_str:
                            continue
                        if hdr_str.startswith("sl. no. | sector | projects") or hdr_str.startswith("sl. no. | state | projects"):
                            continue
                        if "list of completed projects" in hdr_str or "list of deleted projects" in hdr_str:
                            active_col_map = None
                            break

                        col_map = {}
                        score = 0
                        for idx, h in enumerate(row_cells):
                            if "project id" in h:
                                col_map["project_id"] = idx
                                score += 2
                            elif "project name" in h or h == "project" or "project" in h:
                                col_map["project_cell"] = idx
                                score += 2
                            if "state" in h:
                                col_map["state"] = idx
                                score += 1
                            if "sector" in h:
                                col_map["sector"] = idx
                                score += 1
                            if "approval" in h:
                                col_map["approval"] = idx
                                score += 1
                            if "commissioning" in h or "completion" in h or "doc" in h:
                                col_map["doc"] = idx
                                score += 1
                            if "cost" in h and "revised" not in h and "cumulative" not in h:
                                col_map["cost"] = idx
                                score += 1
                            if "revised cost" in h:
                                col_map["revised_cost"] = idx
                                score += 1
                            if "original cost" in h:
                                col_map["original_cost"] = idx
                                score += 1
                            if "expenditure" in h:
                                col_map["expenditure"] = idx
                                score += 1
                            if "progress" in h:
                                col_map["progress"] = idx
                                score += 1

                        if ("project_id" in col_map or "project_cell" in col_map) and score >= 3:
                            if score > best_score:
                                best_score = score
                                best_header_row_idx = r_idx
                                best_header_col_map = col_map

                    if best_header_col_map is not None:
                        active_col_map = best_header_col_map
                        table_data_rows = table[best_header_row_idx + 1:]
                    elif active_col_map and len(table[0]) >= 4:
                        table_data_rows = table
                    else:
                        continue

                    for row in table_data_rows:
                        if not row or len(row) < 3:
                            continue

                        if len(row) > 1 and row[1]:
                            cell1_clean = clean(row[1]).upper()
                            if cell1_clean in INDIAN_STATES:
                                current_state = cell1_clean
                                continue
                            elif len(clean(row[1])) > 3 and not any(c.isdigit() for c in clean(row[1])) and all(not row[i] for i in range(2, len(row))):
                                current_sector = clean(row[1])
                                continue

                        project_id = None
                        project_name = ""
                        agency = None
                        state_in_cell = None

                        proj_cell_idx = active_col_map.get("project_cell", 1)
                        if proj_cell_idx < len(row) and row[proj_cell_idx]:
                            pid, pname, ag, st_cell = self.parse_project_block(row[proj_cell_idx])
                            if pid:
                                project_id = pid
                                project_name = pname
                                agency = ag
                                state_in_cell = st_cell

                        if not project_id:
                            continue

                        state = state_in_cell or current_state or "CENTRAL / MULTI-STATE"
                        if not agency:
                            agency = current_sector or "Central Sector"

                        original_cost = None
                        revised_cost = None
                        anticipated_cost = None

                        if "original_cost" in active_col_map and active_col_map["original_cost"] < len(row) and row[active_col_map["original_cost"]]:
                            original_cost = self.clean_number(row[active_col_map["original_cost"]])
                        if "revised_cost" in active_col_map and active_col_map["revised_cost"] < len(row) and row[active_col_map["revised_cost"]]:
                            revised_cost = self.clean_number(row[active_col_map["revised_cost"]])
                            anticipated_cost = revised_cost
                        if "cost" in active_col_map and active_col_map["cost"] < len(row) and row[active_col_map["cost"]]:
                            oc, rc, ac = self.parse_costs_from_cell(row[active_col_map["cost"]])
                            if original_cost is None:
                                original_cost = oc
                            if revised_cost is None:
                                revised_cost = rc
                            if anticipated_cost is None:
                                anticipated_cost = ac

                        if anticipated_cost is None:
                            anticipated_cost = revised_cost or original_cost

                        expenditure = None
                        if "expenditure" in active_col_map and active_col_map["expenditure"] < len(row) and row[active_col_map["expenditure"]]:
                            exp_val = clean(row[active_col_map["expenditure"]])
                            nums = re.findall(r"[\d,]+(?:\.\d+)?", exp_val)
                            if nums:
                                expenditure = self.clean_number(nums[0])

                        physical_progress = None
                        if "progress" in active_col_map and active_col_map["progress"] < len(row) and row[active_col_map["progress"]]:
                            physical_progress = self.clean_number(row[active_col_map["progress"]])

                        original_completion = None
                        revised_completion = None
                        anticipated_completion = None
                        if "doc" in active_col_map and active_col_map["doc"] < len(row) and row[active_col_map["doc"]]:
                            oc_d, rc_d, ac_d = self.parse_dates_from_cell(row[active_col_map["doc"]])
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
        for r in rows:
            key = (r["project_id"], r["report_month"])
            unique[key] = r

        return list(unique.values())

