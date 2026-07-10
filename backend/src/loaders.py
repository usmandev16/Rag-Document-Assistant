import re
from io import BytesIO

import pandas as pd
from docx import Document
from pypdf import PdfReader

_DATE_NAME_RE = re.compile(r"date|time", re.IGNORECASE)


def _fix_excel_serial_dates(df: pd.DataFrame) -> pd.DataFrame:
    """openpyxl only parses a cell as a date when the source file's own
    number-format says so; a date column stored as plain numbers survives as
    a raw Excel serial (e.g. 46204) instead of a real date. Reinterpret any
    numeric column whose name looks date-like as an Excel serial date."""
    for col in df.columns:
        if not _DATE_NAME_RE.search(str(col)):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_datetime(
                df[col], unit="D", origin="1899-12-30", errors="coerce"
            ).dt.strftime("%Y-%m-%d")
    return df


def _dataframe_to_text(df: pd.DataFrame) -> str:
    """Render a table so every value stays attached to its column header.

    Each row becomes "Col A: v1 | Col B: v2 | ...", one row per paragraph
    (blank-line separated) so the chunker (which only ever splits a
    paragraph that alone exceeds chunk_size) packs whole rows into chunks
    instead of cutting a row — and the ID inside it — in half.
    """
    df = _fix_excel_serial_dates(df.copy())
    df = df.fillna("")
    columns = [str(c) for c in df.columns]
    lines = []
    for _, row in df.iterrows():
        cells = [f"{col}: {row[orig]}" for col, orig in zip(columns, df.columns)]
        lines.append(" | ".join(cells))
    return "\n\n".join(lines)


def extract_text(file_name: str, file_bytes: bytes) -> str:
    name = file_name.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    if name.endswith(".docx"):
        document = Document(BytesIO(file_bytes))
        return "\n\n".join(p.text for p in document.paragraphs if p.text)
    if name.endswith(".xlsx"):
        sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
        parts = []
        for sheet_name, df in sheets.items():
            parts.append(f"# Sheet: {sheet_name}")
            parts.append(_dataframe_to_text(df))
        return "\n\n".join(parts)
    if name.endswith(".csv"):
        df = pd.read_csv(BytesIO(file_bytes))
        return _dataframe_to_text(df)
    return file_bytes.decode("utf-8", errors="ignore")
