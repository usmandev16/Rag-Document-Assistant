"""Spreadsheets as DataFrames: storage at ingestion, and safe query execution.

Uploaded Excel/CSV sheets are saved as parquet per chat, so counting/total
questions can be computed over every row instead of the few chunks that fit
the LLM's token budget. The LLM only ever produces a JSON query plan; it is
validated here and run with the fixed pandas code below — never exec'd.
"""
import json
import os
import re
import shutil
import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd

from src.loaders import _fix_excel_serial_dates

# Per-chat folders: STORAGE_DIR/<chat_id>/{sheets.json, <id>.parquet}. The API
# and worker containers share it through the user-data volume.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "storage"))
MANIFEST = "sheets.json"

OPS = {"==", "!=", ">", "<", "contains"}
FUNCS = {"count", "sum", "mean", "max", "min"}
MAX_GROUPS = 15      # grouped results sent to the LLM, largest first
SAMPLE_VALUES = 3    # example values per column shown to the planner

_CHAT_ID_RE = re.compile(r"[\w-]+")


class PlanError(ValueError):
    """The query plan can't be run against this sheet."""


def _chat_dir(chat_id: str) -> Path:
    # chat_id becomes a path: allow only ids the app itself generates.
    if not _CHAT_ID_RE.fullmatch(chat_id):
        raise ValueError(f"invalid chat id: {chat_id!r}")
    return STORAGE_DIR / chat_id


def list_sheets(chat_id: str) -> list[dict]:
    """[{name, source, sheet, file, columns}] for every sheet in the chat."""
    path = _chat_dir(chat_id) / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = _fix_excel_serial_dates(df.copy())
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            # Mixed int/str columns can't be written to parquet; keep them as text.
            df[col] = df[col].map(lambda v: v if pd.isna(v) else str(v)).astype("string")
    return df


def save_sheets(chat_id: str, file_name: str, file_bytes: bytes) -> int:
    """Save every sheet of an .xlsx/.csv upload as parquet; returns how many.
    Re-uploading the same file name replaces its sheets.

    the manifest is read-modify-write, so two uploads to the same
    chat finishing at the same instant could drop one entry. Uploads to one
    chat are rare enough; use a per-chat lock if that changes."""
    name = file_name.lower()
    if name.endswith(".xlsx"):
        frames = pd.read_excel(BytesIO(file_bytes), sheet_name=None)
    elif name.endswith(".csv"):
        frames = {None: pd.read_csv(BytesIO(file_bytes))}
    else:
        return 0

    folder = _chat_dir(chat_id)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = list_sheets(chat_id)
    for old in [s for s in manifest if s["source"] == file_name]:
        (folder / old["file"]).unlink(missing_ok=True)
    manifest = [s for s in manifest if s["source"] != file_name]

    for sheet, df in frames.items():
        df = _prepare(df)
        file = f"{uuid.uuid4().hex}.parquet"
        df.to_parquet(folder / file, index=False)
        manifest.append({
            "name": file_name if sheet is None else f"{file_name} / {sheet}",
            "source": file_name,
            "sheet": None if sheet is None else str(sheet),
            "file": file,
            "columns": list(df.columns),
        })

    tmp = folder / f"{MANIFEST}.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    tmp.replace(folder / MANIFEST)  # atomic: readers never see a half-written manifest
    return len(frames)


def delete_sheets(chat_id: str) -> None:
    shutil.rmtree(_chat_dir(chat_id), ignore_errors=True)


def load_sheet(chat_id: str, entry: dict) -> pd.DataFrame:
    return pd.read_parquet(_chat_dir(chat_id) / entry["file"])


def describe_sheet(chat_id: str, entry: dict) -> str:
    """Columns with a few example values, so the planner matches the data's
    real formats (e.g. "01 September 2026", "KARACHI")."""
    df = load_sheet(chat_id, entry)
    lines = [f"Sheet {entry['name']!r} ({len(df)} rows). Columns:"]
    for col in df.columns:
        samples = [str(v)[:40] for v in df[col].dropna().unique()[:SAMPLE_VALUES]]
        kind = "number" if pd.api.types.is_numeric_dtype(df[col]) else "text"
        lines.append(f"- {col!r} ({kind}), e.g. {samples}")
    return "\n".join(lines)


def validate_plan(plan: dict, sheets: list[dict]) -> dict:
    """Check the plan against the real sheets; return the sheet entry or
    raise PlanError. Only the fixed ops/funcs and existing columns pass."""
    entry = next((s for s in sheets if s["name"] == plan.get("sheet")), None)
    if entry is None:
        raise PlanError(f"unknown sheet {plan.get('sheet')!r}")
    columns = set(entry["columns"])

    for f in plan.get("filters") or []:
        if f.get("column") not in columns:
            raise PlanError(f"unknown column {f.get('column')!r}")
        if f.get("op") not in OPS:
            raise PlanError(f"unsupported op {f.get('op')!r}")
        if f.get("value") is None:
            raise PlanError(f"filter on {f['column']!r} has no value")
        if f["op"] in (">", "<"):
            try:
                float(f["value"])
            except (TypeError, ValueError):
                raise PlanError(f"{f['op']} needs a number, got {f['value']!r}") from None

    group_by = plan.get("group_by")
    if group_by is not None and group_by not in columns:
        raise PlanError(f"unknown group_by column {group_by!r}")

    agg = plan.get("aggregate") or {}
    if agg.get("func") not in FUNCS:
        raise PlanError(f"unsupported func {agg.get('func')!r}")
    column = agg.get("column")
    if column is None and agg["func"] != "count":
        raise PlanError(f"{agg['func']} needs a column")
    if column is not None and column not in columns:
        raise PlanError(f"unknown column {column!r}")
    return entry


def _filter_mask(df: pd.DataFrame, f: dict) -> pd.Series:
    col, op, value = df[f["column"]], f["op"], f["value"]
    numeric = pd.api.types.is_numeric_dtype(col)
    if op in (">", "<"):
        num = pd.to_numeric(col, errors="coerce")
        if num.isna().all():
            raise PlanError(f"column {f['column']!r} has no numbers to compare")
        mask = num > float(value) if op == ">" else num < float(value)
    elif op == "contains":
        mask = col.astype("string").str.contains(str(value), case=False, regex=False)
    else:
        if numeric:
            try:
                equal = col == float(value)
            except (TypeError, ValueError):
                raise PlanError(f"column {f['column']!r} is numeric, got {value!r}") from None
        else:
            # Case/whitespace-insensitive: "Karachi" matches "KARACHI ".
            equal = col.astype("string").str.strip().str.casefold() == str(value).strip().casefold()
        mask = equal if op == "==" else ~equal.fillna(False)
    return mask.fillna(False).astype(bool)


def _reduce(frame: pd.DataFrame, func: str, column: str | None) -> float | int | None:
    if func == "count":
        return int(len(frame)) if column is None else int(frame[column].notna().sum())
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    result = getattr(values, func)()
    return round(float(result), 2)


def execute_plan(chat_id: str, entry: dict, plan: dict) -> dict:
    """Run a validated plan with fixed pandas operations."""
    df = load_sheet(chat_id, entry)
    mask = pd.Series(True, index=df.index)
    for f in plan.get("filters") or []:
        mask &= _filter_mask(df, f)
    rows = df[mask]

    func, column = plan["aggregate"]["func"], plan["aggregate"].get("column")
    if func != "count" and pd.to_numeric(df[column], errors="coerce").isna().all():
        raise PlanError(f"column {column!r} is not numeric, can't {func} it")

    result = {
        "source": entry["source"],
        "sheet": entry["name"],
        "rows_in_sheet": int(len(df)),
        "rows_matching_filters": int(len(rows)),
        "aggregate": f"{func}({column or 'rows'})",
    }
    group_by = plan.get("group_by")
    if group_by:
        keys = rows[group_by].astype("string").fillna("(blank)")
        values = {key: _reduce(frame, func, column) for key, frame in rows.groupby(keys)}
        ranked = sorted(values.items(), key=lambda kv: (kv[1] is None, -(kv[1] or 0)))
        result["group_count"] = len(ranked)
        result["groups_largest_first"] = [{"group": k, "value": v} for k, v in ranked[:MAX_GROUPS]]
    else:
        result["value"] = _reduce(rows, func, column)
    return result


if __name__ == "__main__":
    # Self-check: python -m src.sheets
    import tempfile

    STORAGE_DIR = Path(tempfile.mkdtemp())  # noqa: F811
    csv = b"City,Status,COD\nKarachi,Delivered,100\nLAHORE,Delivered,250\nkarachi ,Returned,50\nLahore,Booked,x\n"
    assert save_sheets("t1", "s.csv", csv) == 1
    sheets = list_sheets("t1")
    assert sheets[0]["columns"] == ["City", "Status", "COD"]

    def run(plan):
        return execute_plan("t1", validate_plan(plan, sheets), plan)

    base = {"sheet": "s.csv", "filters": [], "group_by": None}
    assert run({**base, "aggregate": {"func": "count", "column": None}})["value"] == 4
    karachi = [{"column": "City", "op": "==", "value": "KARACHI"}]
    assert run({**base, "filters": karachi, "aggregate": {"func": "count", "column": None}})["value"] == 2
    assert run({**base, "filters": [{"column": "Status", "op": "contains", "value": "deliv"}],
                "aggregate": {"func": "sum", "column": "COD"}})["value"] == 350
    assert run({**base, "aggregate": {"func": "max", "column": "COD"}})["value"] == 250
    grouped = run({**base, "group_by": "Status", "aggregate": {"func": "count", "column": None}})
    assert grouped["groups_largest_first"][0] == {"group": "Delivered", "value": 2}
    for bad in [{**base, "sheet": "nope", "aggregate": {"func": "count", "column": None}},
                {**base, "aggregate": {"func": "median", "column": "COD"}},
                {**base, "aggregate": {"func": "sum", "column": "Missing"}},
                {**base, "filters": [{"column": "COD", "op": ">=", "value": "1"}], "aggregate": {"func": "count", "column": None}},
                {**base, "filters": [{"column": "COD", "op": ">", "value": "abc"}], "aggregate": {"func": "count", "column": None}},
                {**base, "aggregate": {"func": "sum", "column": "City"}}]:
        try:
            run(bad)
        except PlanError:
            continue
        raise AssertionError(f"plan should be rejected: {bad}")
    try:
        _chat_dir("../etc")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal not blocked")
    print("sheets self-check OK")
