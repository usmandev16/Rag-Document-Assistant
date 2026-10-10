import re
from io import BytesIO

import pandas as pd
from docx import Document
from pypdf import PdfReader

from src.chunking import chunk_text

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


ROWS_PER_CHUNK = 25


def _dataframe_chunks(df: pd.DataFrame, label: str = "") -> list[str]:
    """Split a table into chunks of ROWS_PER_CHUNK whole rows, each starting
    with the header row ("Col A | Col B | ...") so every chunk is
    self-describing. Rows are never cut, so an ID inside one stays intact.
    Header-once instead of "Col: value" per cell keeps chunks much smaller
    in tokens (Groq free tier: 8k tokens/minute).
    """
    df = _fix_excel_serial_dates(df.copy()).fillna("")
    header = " | ".join(str(c) for c in df.columns)
    rows = [" | ".join(str(v) for v in row) for row in df.itertuples(index=False)]
    prefix = f"{label}\n" if label else ""
    return [
        f"{prefix}{header}\n" + "\n".join(rows[i:i + ROWS_PER_CHUNK])
        for i in range(0, len(rows), ROWS_PER_CHUNK)
    ]


def extract_chunks(file_name: str, file_bytes: bytes) -> list[str]:
    """File -> chunks. Spreadsheets are chunked by rows (header repeated);
    everything else goes through the paragraph-packing text chunker."""
    name = file_name.lower()
    if name.endswith(".xlsx"):
        sheets = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
        return [c for sheet, df in sheets.items() for c in _dataframe_chunks(df, f"# Sheet: {sheet}")]
    if name.endswith(".csv"):
        return _dataframe_chunks(pd.read_csv(BytesIO(file_bytes)))
    return chunk_text(extract_text(file_name, file_bytes), chunk_size=800, overlap=150)


def extract_text(file_name: str, file_bytes: bytes) -> str:
    name = file_name.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    if name.endswith(".docx"):
        document = Document(BytesIO(file_bytes))
        return "\n\n".join(p.text for p in document.paragraphs if p.text)
    return file_bytes.decode("utf-8", errors="ignore")
