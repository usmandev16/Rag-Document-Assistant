"""Summarize every run in loadtest/results: Locust totals, the system's own
time (total minus fake-LLM time, when raw_<run>.csv exists) and API CPU from
docker stats. Writes loadtest/results/summary.md and prints it."""
import csv
import re
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"


def pct(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p * len(values))) - 1)]


def api_cpu(name: str, users: int) -> str:
    """Median API CPU % during the run (per core: 800% = all 8 cores busy)."""
    # First runs were saved as docker_stats_<users>.csv; later runs use the run name.
    paths = [OUT / f"docker_stats_{name}.csv"] + ([OUT / f"docker_stats_{users}.csv"] if name.startswith("step_") else [])
    for path in paths:
        if path.exists():
            cpu = [float(r[1].rstrip("%")) for r in csv.reader(path.read_text(encoding="utf-8").splitlines())
                   if len(r) == 3 and "api" in r[0]]
            if cpu:
                return f"{statistics.median(cpu):.0f}%"
    return "not sampled"


def system_time(name: str) -> str:
    """p50 / p95 of total minus fake-LLM time per request."""
    path = OUT / f"raw_{name}.csv"
    if not path.exists():
        return "not measured"
    own = [float(r["total_ms"]) - float(r["llm_stub_ms"]) for r in csv.DictReader(path.open(encoding="utf-8"))]
    return f"{pct(own, 0.5):.0f} / {pct(own, 0.95):.0f} ms" if own else "no rows"


rows = []
for stats_file in sorted(OUT.glob("*_stats.csv")):
    name = stats_file.name.removesuffix("_stats.csv")
    match = re.match(r".*?_(\d+)(?:_run\d+)?$", name)
    if not match:
        continue
    users = int(match.group(1))
    total = next(r for r in csv.DictReader(stats_file.open(encoding="utf-8")) if r["Name"] == "Aggregated")
    requests, failures = int(total["Request Count"]), int(total["Failure Count"])
    rows.append((name, users, f"| {name} | {users} | {requests} | {float(total['Requests/s']):.1f} "
                              f"| {total['50%']} | {total['95%']} | {100 * failures / max(requests, 1):.1f}% "
                              f"| {system_time(name)} | {api_cpu(name, users)} |"))

table = "\n".join([
    "| Run | Users | Requests | Req/s | p50 ms | p95 ms | Errors | System p50 / p95 | API CPU (median) |",
    "|---|---|---|---|---|---|---|---|---|",
    *(line for _, _, line in sorted(rows, key=lambda r: (r[1], r[0]))),
])
(OUT / "summary.md").write_text(table + "\n", encoding="utf-8")
print(table)
