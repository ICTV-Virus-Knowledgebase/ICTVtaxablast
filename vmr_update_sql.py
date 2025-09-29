#!/usr/bin/env python3
"""Generate SQL update and insert scripts from an ICTV VMR workbook."""

from __future__ import annotations

import argparse
import math
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Integral, Real
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import pandas as pd

DEFAULT_WORKBOOK = Path("./VMRs/VMR_MSL40.v1.20250307.editor_DBS_22 July.xlsx")
ERROR_FILENAME = "errors.xlsx"
DELETES_FILENAME = "vmr_1_deletes.sql"
UPDATES_FILENAME = "vmr_2_updates.sql"
INSERTS_FILENAME = "vmr_3_inserts.sql"
VERSION_FILE = Path("version_git.txt")

# Columns A:AG that must appear (in order) on the worksheets we process.
REQUIRED_COLUMNS: List[str] = [
    "Isolate ID",
    "Species Sort",
    "Isolate Sort",
    "Realm",
    "Subrealm",
    "Kingdom",
    "Subkingdom",
    "Phylum",
    "Subphylum",
    "Class",
    "Subclass",
    "Order",
    "Suborder",
    "Family",
    "Subfamily",
    "Genus",
    "Subgenus",
    "Species",
    "ICTV_ID",
    "Exemplar or additional isolate",
    "Virus name(s)",
    "Virus name abbreviation(s)",
    "Virus isolate designation",
    "Virus GENBANK accession",
    "Genome coverage",
    "Genome",
    "Host source",
    "Accessions Link",
    "Editor Notes",
    "QC_status",
    "QC_taxon_inher_molecule",
    "QC_taxon_change",
    "QC_taxon_proposal",
]

READ_ONLY_COLUMNS = {
    "Isolate ID",
    "Species Sort",
    "Realm",
    "Subrealm",
    "Kingdom",
    "Subkingdom",
    "Phylum",
    "Subphylum",
    "Class",
    "Subclass",
    "Order",
    "Suborder",
    "Family",
    "Subfamily",
    "Genus",
    "Subgenus",
    "ICTV_ID",
    "Accessions Link",
}

# Mapping of VMR columns to SQL columns when generating UPDATE statements.
UPDATABLE_TO_SQL = {
    "Isolate Sort": "isolate_sort",
    "Species": "species_name",
    "Exemplar or additional isolate": "isolate_type",
    "Virus name(s)": "isolate_names",
    "Virus name abbreviation(s)": "isolate_abbrevs",
    "Virus isolate designation": "isolate_designation",
    "Virus GENBANK accession": "genbank_accessions",
    "Genome coverage": "genome_coverage",
    "Genome": "molecule",
    "Host source": "host_source",
    "Editor Notes": "notes",
}

# Mapping used when creating INSERT statements for new records.
INSERT_COLUMN_MAPPING: Sequence[Tuple[str, str]] = (
    ("taxnode_id", "ICTV_ID"),
    ("species_sort", "Species Sort"),
    ("isolate_sort", "Isolate Sort"),
    ("species_name", "Species"),
    ("isolate_type", "Exemplar or additional isolate"),
    ("isolate_names", "Virus name(s)"),
    ("isolate_abbrevs", "Virus name abbreviation(s)"),
    ("isolate_designation", "Virus isolate designation"),
    ("genbank_accessions", "Virus GENBANK accession"),
    ("genome_coverage", "Genome coverage"),
    ("molecule", "Genome"),
    ("host_source", "Host source"),
    ("accession_links", "Accessions Link"),
    ("notes", "Editor Notes"),
)

INT_COLUMNS = {"taxnode_id", "species_sort", "isolate_sort"}
INVALID_VALUE = object()


class ProcessingHalted(Exception):
    """Raised when validation should stop immediately."""


@dataclass
class ErrorEntry:
    filename: str
    worksheet: str
    row: Optional[int]
    message: str
    severity: str


@dataclass
class UpdateEntry:
    isolate_id: str
    numeric_id: int
    row_number: int
    assignments: List[Tuple[str, Optional[object]]]


@dataclass
class InsertEntry:
    row_number: int
    values: List[Tuple[str, Optional[object]]]


@dataclass
class DeleteEntry:
    isolate_id: str
    target_value: str
    row_number: int
    details: List[Tuple[str, Optional[object]]]


@dataclass
class ProcessResult:
    updated_sheet: Optional[str]
    delete_entries: List[DeleteEntry]
    update_entries: List[UpdateEntry]
    insert_entries: List[InsertEntry]


class ErrorCollector:
    """Collects errors and enforces the stop/continue policy."""

    def __init__(self, keep_going: bool, command: str, version: str, run_date: str) -> None:
        self.keep_going = keep_going
        self.entries: List[ErrorEntry] = []
        self.command = command
        self.version = version
        self.run_date = run_date

    def add(
        self,
        filename: str,
        worksheet: str,
        row: Optional[int],
        message: str,
        *,
        severity: str = "ERROR",
    ) -> None:
        entry = ErrorEntry(filename, worksheet, row, message, severity)
        self.entries.append(entry)
        location = filename
        if worksheet:
            location += f"::{worksheet}"
        if row is not None:
            location += f" row {row}"
        print(f"{severity.upper()}: {location} - {message}", file=sys.stderr)
        if severity.upper() == "ERROR" and not self.keep_going:
            raise ProcessingHalted(message)

    def has_errors(self) -> bool:
        return any(entry.severity.upper() == "ERROR" for entry in self.entries)

    def extend_with_exception(self, filename: str, exc: Exception) -> None:
        self.entries.append(
            ErrorEntry(filename, "", None, f"Unhandled exception: {exc!r}", "ERROR")
        )
        print(f"ERROR: {filename} - Unhandled exception: {exc!r}", file=sys.stderr)

    def write_excel(self, output_path: Path) -> None:
        data = {
            "filename": [entry.filename for entry in self.entries],
            "worksheet": [entry.worksheet for entry in self.entries],
            "row": [entry.row for entry in self.entries],
            "message": [entry.message for entry in self.entries],
            "severity": [entry.severity for entry in self.entries],
            "command": [self.command for _ in self.entries],
            "version": [self.version for _ in self.entries],
            "run_date": [self.run_date for _ in self.entries],
        }
        df = pd.DataFrame(data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a VMR workbook and generate MariaDB SQL update and insert scripts."
        )
    )
    parser.add_argument(
        "workbook",
        nargs="?",
        default=str(DEFAULT_WORKBOOK),
        help="Path to the VMR Excel workbook (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help=(
            "Directory where SQL and error reports are written. Default is the"
            " workbook filename without the .xlsx suffix."
        ),
    )
    parser.add_argument(
        "-k",
        "--keep-going",
        action="store_true",
        help="Continue processing after encountering validation errors.",
    )
    parser.add_argument(
        "--strict-accession",
        action="store_true",
        help=(
            "Emit warnings for accession changes that only adjust whitespace, "
            "segment labels, or populate previously empty values."
        ),
    )
    parser.add_argument(
        "--updates-sql",
        default=UPDATES_FILENAME,
        help="Filename for UPDATE statements (default: %(default)s)",
    )
    parser.add_argument(
        "--deletes-sql",
        default=DELETES_FILENAME,
        help="Filename for DELETE statements (default: %(default)s)",
    )
    parser.add_argument(
        "--inserts-sql",
        default=INSERTS_FILENAME,
        help="Filename for INSERT statements (default: %(default)s)",
    )
    parser.add_argument(
        "--errors-xlsx",
        default=ERROR_FILENAME,
        help="Filename for the error report workbook (default: %(default)s)",
    )
    return parser.parse_args()


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    fallback = Path("version.txt")
    if fallback.exists():
        return fallback.read_text(encoding="utf-8").strip()
    return "unknown"


def normalize_string(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, bytes):
        stripped = value.decode("utf-8", errors="ignore").strip()
        return stripped or None
    if isinstance(value, Real):
        if isinstance(value, float) and math.isnan(value):
            return None
        return str(value)
    return str(value).strip() or None


def is_abolish_value(value: object) -> bool:
    text = normalize_string(value)
    return text is not None and text.lower() == "abolish"


def normalize_int_like(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        if math.isnan(value):
            return None
        if float(value).is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            number = float(stripped)
        except ValueError:
            return None
        if math.isnan(number):
            return None
        if number.is_integer():
            return int(number)
        return None
    return None


def normalize_isolate_type(value: object) -> Optional[str]:
    text = normalize_string(value)
    if text is None:
        return None
    text = text.upper()
    if text in {"E", "A"}:
        return text
    if text.startswith("EXEM"):
        return "E"
    if text.startswith("ADD"):
        return "A"
    return None


def values_equal(original: object, updated: object, column: str) -> bool:
    if column == "Exemplar or additional isolate":
        return normalize_isolate_type(original) == normalize_isolate_type(updated)
    if column in {"Isolate Sort", "Species Sort"}:
        return normalize_int_like(original) == normalize_int_like(updated)
    return normalize_string(original) == normalize_string(updated)


def normalize_isolate_id(value: object) -> Optional[str]:
    text = normalize_string(value)
    if not text:
        return None
    return text.upper()


def extract_isolate_numeric(isolate_id: str) -> Optional[int]:
    match = re.fullmatch(r"VMR(\d+)", isolate_id)
    if not match:
        return None
    return int(match.group(1))


def excel_row(index: int) -> int:
    return int(index) + 2


def validate_headers(
    filename: str,
    sheet_name: str,
    actual_columns: Sequence[str],
    errors: ErrorCollector,
) -> None:
    expected_len = len(REQUIRED_COLUMNS)
    if len(actual_columns) < expected_len:
        missing = REQUIRED_COLUMNS[len(actual_columns) :]
        errors.add(
            filename,
            sheet_name,
            None,
            "Worksheet is missing required columns: " + ", ".join(missing),
        )
        return
    for idx, expected in enumerate(REQUIRED_COLUMNS):
        actual = actual_columns[idx]
        if actual != expected:
            errors.add(
                filename,
                sheet_name,
                None,
                f"Column {idx + 1} mismatch: expected '{expected}' but found '{actual}'",
            )


def prepare_dataframe(workbook: Path, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(workbook, sheet_name=sheet_name, usecols=REQUIRED_COLUMNS)
    df = df.copy()
    df["__row_number"] = (df.index + 2).astype(int)
    df["__isolate_id"] = df["Isolate ID"].apply(normalize_isolate_id)
    return df


def determine_updated_sheet(
    sheet_names: Sequence[str], workbook_name: str, errors: ErrorCollector
) -> Optional[str]:
    pattern = re.compile(r"VMR MSL\d+")
    matches = [name for name in sheet_names if pattern.fullmatch(name)]
    if not matches:
        errors.add(
            workbook_name,
            "",
            None,
            "Workbook does not contain a worksheet named like 'VMR MSL[0-9]+'.",
        )
        return None
    if len(matches) > 1:
        errors.add(
            workbook_name,
            "",
            None,
            "Multiple updated worksheets found: " + ", ".join(matches),
        )
    return matches[0]


def check_original_ids(original_df: pd.DataFrame, workbook_name: str, errors: ErrorCollector) -> None:
    for _, row in original_df.iterrows():
        if row["__isolate_id"] is None:
            errors.add(
                workbook_name,
                "Original",
                int(row["__row_number"]),
                "Original worksheet contains a blank Isolate ID.",
            )


def check_isolate_ids(
    updated_df: pd.DataFrame,
    original_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
) -> None:
    updated_existing = updated_df[updated_df["__isolate_id"].notna()]
    original_existing = original_df[original_df["__isolate_id"].notna()]

    for df, sheet in ((updated_existing, updated_sheet), (original_existing, "Original")):
        for _, row in df.iterrows():
            isolate_id = row["__isolate_id"]
            if isolate_id and not re.fullmatch(r"VMR\d+", isolate_id):
                errors.add(
                    workbook_name,
                    sheet,
                    int(row["__row_number"]),
                    f"Invalid Isolate ID format: {row['Isolate ID']}",
                )

    for df, sheet in ((updated_existing, updated_sheet), (original_existing, "Original")):
        counts = df["__isolate_id"].value_counts()
        for isolate_id, count in counts.items():
            if count > 1:
                rows = df.loc[df["__isolate_id"] == isolate_id, "__row_number"].astype(int).tolist()
                rows_str = ", ".join(str(r) for r in rows)
                errors.add(
                    workbook_name,
                    sheet,
                    rows[0],
                    f"Isolate ID {isolate_id} appears multiple times (rows {rows_str}).",
                )

    updated_ids = set(updated_existing["__isolate_id"])
    original_ids = set(original_existing["__isolate_id"])

    for isolate_id in sorted(updated_ids - original_ids):
        row_num = int(
            updated_existing.loc[updated_existing["__isolate_id"] == isolate_id, "__row_number"].iloc[0]
        )
        errors.add(
            workbook_name,
            updated_sheet,
            row_num,
            f"Isolate ID {isolate_id} not present in Original worksheet.",
        )

    for isolate_id in sorted(original_ids - updated_ids):
        row_num = int(
            original_existing.loc[original_existing["__isolate_id"] == isolate_id, "__row_number"].iloc[0]
        )
        errors.add(
            workbook_name,
            "Original",
            row_num,
            f"Isolate ID {isolate_id} missing from updated worksheet.",
        )


def enforce_read_only(
    updated_df: pd.DataFrame,
    original_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
    abolished_ids: set[str],
) -> None:
    updated_map = updated_df.set_index("__isolate_id")
    original_map = original_df.set_index("__isolate_id")
    for isolate_id, orig_row in original_map.iterrows():
        if isolate_id not in updated_map.index or isolate_id is None:
            continue
        upd_row = updated_map.loc[isolate_id]
        if isinstance(upd_row, pd.DataFrame):
            continue
        if isolate_id in abolished_ids:
            continue
        for column in READ_ONLY_COLUMNS:
            if column == "Isolate ID":
                continue
            if not values_equal(orig_row[column], upd_row[column], column):
                errors.add(
                    workbook_name,
                    updated_sheet,
                    int(upd_row["__row_number"]),
                    f"Read-only column '{column}' changed for isolate {isolate_id}.",
                )


def split_accession_entries(value: object) -> List[Tuple[Optional[str], str]]:
    """Return segment/accession pairs extracted from a worksheet cell."""

    text = normalize_string(value)
    if not text:
        return []
    entries: List[Tuple[Optional[str], str]] = []
    for fragment in re.split(r"[;\n]+", text):
        part = fragment.strip()
        if not part:
            continue
        segment: Optional[str] = None
        accession = part
        if ":" in part:
            segment_text, accession_text = part.split(":", 1)
            segment = segment_text.strip() or None
            accession = accession_text.strip()
        if accession:
            entries.append((segment, accession))
    return entries


def canonicalize_accession_entries(
    entries: List[Tuple[Optional[str], str]], include_segment_names: bool
) -> List[Tuple[str, str]]:
    """Build a normalized representation of accession entries."""

    canonical: List[Tuple[str, str]] = []
    for segment, accession in entries:
        accession_norm = accession.upper()
        if include_segment_names:
            segment_norm = (segment or "").upper()
        else:
            segment_norm = ""
        canonical.append((segment_norm, accession_norm))
    return canonical


def classify_accession_change(original: object, updated: object) -> str:
    """Classify how the accession field changed between two values."""

    orig_entries = split_accession_entries(original)
    upd_entries = split_accession_entries(updated)

    if not orig_entries:
        if not upd_entries:
            return "whitespace"
        if normalize_string(original) is None:
            return "was_empty"
    if not upd_entries:
        if orig_entries:
            return "meaningful"
        return "whitespace"

    if canonicalize_accession_entries(orig_entries, True) == canonicalize_accession_entries(
        upd_entries, True
    ):
        return "whitespace"
    if canonicalize_accession_entries(orig_entries, False) == canonicalize_accession_entries(
        upd_entries, False
    ):
        return "segment_name"
    return "meaningful"


def parse_accession_tokens(value: object) -> List[str]:
    return [accession.upper() for _, accession in split_accession_entries(value)]


def check_new_record_accessions(
    updated_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
) -> None:
    new_rows = updated_df[
        (updated_df["__isolate_id"].isna()) & (~updated_df["__abolished"])
    ]
    if new_rows.empty:
        return

    existing_map: dict[str, int] = {}
    existing_rows = updated_df[
        (updated_df["__isolate_id"].notna()) & (~updated_df["__abolished"])
    ]
    for _, row in existing_rows.iterrows():
        row_number = int(row["__row_number"])
        for token in parse_accession_tokens(row["Virus GENBANK accession"]):
            existing_map.setdefault(token, row_number)

    seen_new: dict[str, int] = {}
    for _, row in new_rows.iterrows():
        row_number = int(row["__row_number"])
        tokens = parse_accession_tokens(row["Virus GENBANK accession"])
        duplicates = sorted({token for token in tokens if token in existing_map})
        if duplicates:
            refs = [
                f"{token} (worksheet row {existing_map[token]})" for token in duplicates
            ]
            errors.add(
                workbook_name,
                updated_sheet,
                row_number,
                "New record reuses existing accession(s): " + ", ".join(refs),
            )
            continue
        duplicates_new = sorted({token for token in tokens if token in seen_new})
        if duplicates_new:
            refs = [
                f"{token} (worksheet row {seen_new[token]})" for token in duplicates_new
            ]
            errors.add(
                workbook_name,
                updated_sheet,
                row_number,
                "New record reuses accession(s) from other new rows: "
                + ", ".join(refs),
            )
            continue
        for token in tokens:
            seen_new.setdefault(token, row_number)


def convert_value(
    sql_column: str,
    vmr_value: object,
    vmr_column: str,
    workbook_name: str,
    sheet_name: str,
    row_number: int,
    errors: ErrorCollector,
) -> object:
    text = normalize_string(vmr_value)
    if sql_column == "taxnode_id":
        if text is None:
            return None
        match = re.fullmatch(r"ICTV(\d+)", text.upper())
        if not match:
            errors.add(
                workbook_name,
                sheet_name,
                row_number,
                "Column 'ICTV_ID' must resemble ICTV######## to derive taxnode_id.",
            )
            return INVALID_VALUE
        return int(match.group(1))
    if sql_column in INT_COLUMNS:
        result = normalize_int_like(vmr_value)
        if result is None and text is not None:
            errors.add(
                workbook_name,
                sheet_name,
                row_number,
                f"Column '{vmr_column}' must contain an integer value.",
            )
            return INVALID_VALUE
        return result
    if sql_column == "isolate_type":
        if text is None:
            return None
        result = normalize_isolate_type(vmr_value)
        if result is None:
            errors.add(
                workbook_name,
                sheet_name,
                row_number,
                f"Column '{vmr_column}' must contain 'E' or 'A'.",
            )
            return INVALID_VALUE
        return result
    return text


def build_update_entries(
    updated_df: pd.DataFrame,
    original_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
    *,
    strict_accession: bool,
) -> List[UpdateEntry]:
    entries: List[UpdateEntry] = []
    updated_existing = updated_df[
        (updated_df["__isolate_id"].notna()) & (~updated_df["__abolished"])
    ].set_index("__isolate_id")
    original_existing = original_df[original_df["__isolate_id"].notna()].set_index("__isolate_id")

    for isolate_id, orig_row in original_existing.iterrows():
        if isolate_id not in updated_existing.index:
            continue
        upd_row = updated_existing.loc[isolate_id]
        if isinstance(upd_row, pd.DataFrame):
            continue
        changes: List[Tuple[str, Optional[object]]] = []
        invalid = False
        for vmr_column, sql_column in UPDATABLE_TO_SQL.items():
            orig_value = orig_row[vmr_column]
            upd_value = upd_row[vmr_column]
            if values_equal(orig_value, upd_value, vmr_column):
                continue
            if vmr_column == "Virus GENBANK accession":
                change_type = classify_accession_change(orig_value, upd_value)
                if strict_accession or change_type == "meaningful":
                    errors.add(
                        workbook_name,
                        updated_sheet,
                        int(upd_row["__row_number"]),
                        (
                            "Virus GENBANK accession changed from "
                            f"'{normalize_string(orig_value) or ''}' to "
                            f"'{normalize_string(upd_value) or ''}' for isolate {isolate_id}."
                        ),
                        severity="WARNING",
                    )
            converted = convert_value(
                sql_column,
                upd_value,
                vmr_column,
                workbook_name,
                updated_sheet,
                int(upd_row["__row_number"]),
                errors,
            )
            if converted is INVALID_VALUE:
                invalid = True
                continue
            changes.append((sql_column, converted))
        if invalid or not changes:
            continue
        numeric_id = extract_isolate_numeric(isolate_id)
        if numeric_id is None:
            errors.add(
                workbook_name,
                updated_sheet,
                int(upd_row["__row_number"]),
                f"Isolate ID '{isolate_id}' cannot be converted to numeric form.",
            )
            continue
        entries.append(
            UpdateEntry(
                isolate_id=isolate_id,
                numeric_id=numeric_id,
                row_number=int(upd_row["__row_number"]),
                assignments=changes,
            )
        )
    return entries


def build_insert_entries(
    updated_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
) -> List[InsertEntry]:
    entries: List[InsertEntry] = []
    new_rows = updated_df[
        (updated_df["__isolate_id"].isna()) & (~updated_df["__abolished"])
    ]
    for _, row in new_rows.iterrows():
        row_number = int(row["__row_number"])
        values: List[Tuple[str, Optional[object]]] = []
        invalid = False
        for sql_column, vmr_column in INSERT_COLUMN_MAPPING:
            converted = convert_value(
                sql_column,
                row[vmr_column],
                vmr_column,
                workbook_name,
                updated_sheet,
                row_number,
                errors,
            )
            if converted is INVALID_VALUE:
                invalid = True
            values.append((sql_column, None if converted is INVALID_VALUE else converted))
        if invalid:
            continue
        entries.append(InsertEntry(row_number=row_number, values=values))
    return entries


def build_delete_entries(
    updated_df: pd.DataFrame,
    workbook_name: str,
    updated_sheet: str,
    errors: ErrorCollector,
) -> List[DeleteEntry]:
    entries: List[DeleteEntry] = []
    delete_rows = updated_df[updated_df["__abolished"]]
    for _, row in delete_rows.iterrows():
        row_number = int(row["__row_number"])
        isolate_id = normalize_isolate_id(row["Isolate ID"])
        if not isolate_id:
            errors.add(
                workbook_name,
                updated_sheet,
                row_number,
                "Row marked for abolish must contain an Isolate ID.",
            )
            continue
        target_value = normalize_string(row["Isolate ID"])
        if not target_value:
            errors.add(
                workbook_name,
                updated_sheet,
                row_number,
                "Row marked for abolish must contain an Isolate ID value.",
            )
            continue
        details: List[Tuple[str, Optional[object]]] = []
        for column in REQUIRED_COLUMNS:
            if column == "Species Sort":
                continue
            details.append((column, row[column]))
        entries.append(
            DeleteEntry(
                isolate_id=isolate_id,
                target_value=target_value,
                row_number=row_number,
                details=details,
            )
        )
    return entries


def generate_sql_header(workbook_path: Path, version: str) -> List[str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    return [
        f"-- Source workbook: {workbook_path}",
        f"-- Generated: {timestamp}",
        f"-- Script version: {version}",
        "",
    ]


def format_sql_value(column: str, value: Optional[object]) -> str:
    if value is None:
        return "NULL"
    if column in INT_COLUMNS and isinstance(value, Real):
        return str(int(value))
    if isinstance(value, Integral):
        return str(int(value))
    text = str(value).replace("'", "''")
    return f"'{text}'"


def build_update_sql_text(
    entries: List[UpdateEntry], workbook_path: Path, version: str
) -> str:
    lines = generate_sql_header(workbook_path, version)
    if not entries:
        lines.append("-- No updates required.")
        return "\n".join(lines) + "\n"
    for entry in entries:
        lines.append(f"-- {entry.isolate_id} (worksheet row {entry.row_number})")
        lines.append("UPDATE species_isolates")
        lines.append("SET")
        assignments = [
            f"    {column} = {format_sql_value(column, value)}"
            for column, value in entry.assignments
        ]
        lines.append(",\n".join(assignments))
        lines.append(f"WHERE isolate_id = {entry.numeric_id};")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_insert_sql_text(
    entries: List[InsertEntry], workbook_path: Path, version: str
) -> str:
    lines = generate_sql_header(workbook_path, version)
    if not entries:
        lines.append("-- No inserts required.")
        return "\n".join(lines) + "\n"
    for entry in entries:
        lines.append(f"-- Worksheet row {entry.row_number}")
        columns = [column for column, _ in entry.values]
        values = [format_sql_value(column, value) for column, value in entry.values]
        lines.append("INSERT INTO species_isolates (")
        lines.append("    " + ",\n    ".join(columns))
        lines.append(") VALUES (")
        lines.append("    " + ",\n    ".join(values))
        lines.append(");")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_delete_sql_text(
    entries: List[DeleteEntry], workbook_path: Path, version: str
) -> str:
    lines = generate_sql_header(workbook_path, version)
    if not entries:
        lines.append("-- No deletes required.")
        return "\n".join(lines) + "\n"
    for entry in entries:
        lines.append(f"-- {entry.isolate_id} (worksheet row {entry.row_number})")
        for column, value in entry.details:
            comment_value = normalize_string(value)
            if comment_value is None:
                comment_value = ""
            else:
                comment_value = comment_value.replace("\n", " | ")
            lines.append(f"-- {column}: {comment_value}")
        lines.append("DELETE FROM species_isolates")
        lines.append(
            f"WHERE isolate_id = {format_sql_value('isolate_id', entry.target_value)};"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_placeholder_sql_text(
    workbook_path: Path, version: str, note: str
) -> str:
    lines = generate_sql_header(workbook_path, version)
    lines.append(f"-- {note}")
    return "\n".join(lines) + "\n"


def process_workbook(
    workbook_path: Path,
    workbook_name: str,
    errors: ErrorCollector,
    *,
    strict_accession: bool,
) -> ProcessResult:
    with pd.ExcelFile(workbook_path) as xl:
        sheet_names = xl.sheet_names

    updated_sheet = determine_updated_sheet(sheet_names, workbook_name, errors)
    if updated_sheet is None or "Original" not in sheet_names:
        if "Original" not in sheet_names:
            errors.add(
                workbook_name,
                "",
                None,
                "Workbook does not contain an 'Original' worksheet.",
            )
        return ProcessResult(updated_sheet, [], [], [])

    updated_headers = pd.read_excel(workbook_path, sheet_name=updated_sheet, nrows=0).columns
    validate_headers(workbook_name, updated_sheet, list(updated_headers), errors)

    original_headers = pd.read_excel(workbook_path, sheet_name="Original", nrows=0).columns
    validate_headers(workbook_name, "Original", list(original_headers), errors)

    updated_df = prepare_dataframe(workbook_path, updated_sheet)
    updated_df["__abolished"] = updated_df["Species Sort"].apply(is_abolish_value)
    original_df = prepare_dataframe(workbook_path, "Original")

    check_original_ids(original_df, workbook_name, errors)
    check_isolate_ids(updated_df, original_df, workbook_name, updated_sheet, errors)
    abolished_ids = {
        isolate_id
        for isolate_id in updated_df.loc[updated_df["__abolished"], "__isolate_id"].dropna()
    }
    enforce_read_only(
        updated_df,
        original_df,
        workbook_name,
        updated_sheet,
        errors,
        abolished_ids,
    )
    check_new_record_accessions(updated_df, workbook_name, updated_sheet, errors)

    delete_entries = build_delete_entries(updated_df, workbook_name, updated_sheet, errors)
    update_entries = build_update_entries(
        updated_df,
        original_df,
        workbook_name,
        updated_sheet,
        errors,
        strict_accession=strict_accession,
    )
    insert_entries = build_insert_entries(updated_df, workbook_name, updated_sheet, errors)

    return ProcessResult(updated_sheet, delete_entries, update_entries, insert_entries)


def write_sql_outputs(
    output_dir: Path,
    args: argparse.Namespace,
    result: ProcessResult,
    workbook_path: Path,
    version: str,
    had_errors: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    deletes_path = output_dir / args.deletes_sql
    updates_path = output_dir / args.updates_sql
    inserts_path = output_dir / args.inserts_sql
    workbook_display = workbook_path.resolve()

    if had_errors or result.updated_sheet is None:
        note = "Errors encountered; SQL generation skipped."
        placeholder = build_placeholder_sql_text(workbook_display, version, note)
        deletes_path.write_text(placeholder, encoding="utf-8")
        updates_path.write_text(placeholder, encoding="utf-8")
        inserts_path.write_text(placeholder, encoding="utf-8")
        return

    deletes_sql = build_delete_sql_text(result.delete_entries, workbook_display, version)
    updates_sql = build_update_sql_text(result.update_entries, workbook_display, version)
    inserts_sql = build_insert_sql_text(result.insert_entries, workbook_display, version)
    deletes_path.write_text(deletes_sql, encoding="utf-8")
    updates_path.write_text(updates_sql, encoding="utf-8")
    inserts_path.write_text(inserts_sql, encoding="utf-8")


def main() -> None:
    args = parse_args()
    workbook_path = Path(args.workbook).expanduser()
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
    else:
        output_dir = Path(Path(args.workbook).name).with_suffix("")

    command_line = " ".join(shlex.quote(arg) for arg in sys.argv)
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        subprocess.run(["./version_git.sh"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass
    version = read_version()
    errors = ErrorCollector(
        keep_going=args.keep_going,
        command=command_line,
        version=version,
        run_date=run_timestamp,
    )
    result = ProcessResult(None, [], [], [])

    if not workbook_path.exists():
        errors.add(
            workbook_path.name,
            "",
            None,
            f"Workbook not found: {workbook_path}",
        )
    else:
        try:
            result = process_workbook(
                workbook_path,
                workbook_path.name,
                errors,
                strict_accession=args.strict_accession,
            )
        except ProcessingHalted:
            pass
        except Exception as exc:  # pragma: no cover - defensive programming
            errors.extend_with_exception(workbook_path.name, exc)

    errors.write_excel(output_dir / args.errors_xlsx)
    write_sql_outputs(output_dir, args, result, workbook_path, version, errors.has_errors())

    if errors.has_errors():
        sys.exit(1)


if __name__ == "__main__":
    main()
