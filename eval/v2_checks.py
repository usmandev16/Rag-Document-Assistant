"""Pre-run checks for the held-out eval (v2), against the chunks as ingested.

    python eval/v2_checks.py            (inside the worker container)

Prints: chunks and OCR'd pages per file, keyword-index memory, and for every
question with evidence whether that evidence is in the stored chunks of one of
its source_files (case-insensitive, whitespace collapsed to single spaces).
"""
import collections
import difflib
import json
import resource

import run_eval_v2  # noqa: F401  (points run_eval at the v2 dataset and namespace)
import run_eval as ev
from src import lexical, sheets


def norm(text: str) -> str:
    return " ".join(text.lower().split())


before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
records, bm25 = lexical._index(ev.NAMESPACE)
after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"chunks in the keyword store: {len(records)} | keyword index memory: ~{(after - before) / 1024:.0f} MB "
      f"(process peak {after / 1024:.0f} MB)")
print("sheets:", [(s["name"], len(s["columns"])) for s in sheets.list_sheets(ev.NAMESPACE)])

by_file = collections.defaultdict(list)
for r in records:
    by_file[r["metadata"]["source"]].append(r)
print(f"\n{'file':<62}{'chunks':>7}  OCR'd pages")
for name in sorted(by_file):
    pages = sorted({r["metadata"]["page"] for r in by_file[name] if r["metadata"].get("ocr")})
    print(f"{name[:60]:<62}{len(by_file[name]):>7}  {pages if pages else '-'}")

rows = [r for r in ev.load_dataset(None) if r.get("evidence")]
found = loose = 0
missing = []
for r in rows:
    chunks = [c for f in r["source_files"] for c in by_file.get(f, [])]
    if any(norm(r["evidence"]) in norm(c["text"]) for c in chunks):
        found += 1
    elif any(ev.compact(r["evidence"]) in ev.compact(c["text"]) for c in chunks):
        loose += 1
        missing.append((r, "matches only with ALL whitespace removed"))
    else:
        missing.append((r, "NOT FOUND"))
print(f"\nevidence check: {found}/{len(rows)} found (single-space match); {loose} more match with all whitespace "
      f"removed; {len(rows) - found - loose} not found")
for r, why in missing:
    chunks = [c for f in r["source_files"] for c in by_file.get(f, [])]
    target = norm(r["evidence"])
    best = max(chunks, key=lambda c: difflib.SequenceMatcher(None, target, norm(c["text"]), autojunk=False)
               .find_longest_match().size)
    text = norm(best["text"])
    m = difflib.SequenceMatcher(None, target, text, autojunk=False).find_longest_match()
    lo, hi = max(0, m.b - m.a - 30), m.b - m.a + len(target) + 30
    print(f"\n{r['id']} ({r['type']}) {why}\n  evidence: {r['evidence']!r}\n  nearest ({best['metadata']['source']}, "
          f"chunk {best['metadata']['chunk_index']}, page {best['metadata'].get('page')}, ocr {best['metadata'].get('ocr')}): "
          f"{text[lo:hi]!r}")
print(json.dumps({"checked": len(rows), "found": found, "loose": loose}))
