"""Summarize loadtest/results: one row per step from Locust's CSVs and the
docker stats samples. Writes loadtest/results/summary.md and prints it."""
import csv
import re
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"
UNITS = {"B": 1 / 2**20, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}


def mib(text: str) -> float:
    value, unit = re.match(r"([\d.]+)\s*(\w+)", text.strip()).groups()
    return float(value) * UNITS[unit]


def container_stats(users: int, name: str) -> tuple[float, float, float]:
    """(median CPU %, max CPU %, max memory MiB) of one container during a step.
    Docker reports CPU % per core: 800% = all 8 cores busy."""
    cpu, mem = [], []
    for row in csv.reader((OUT / f"docker_stats_{users}.csv").read_text(encoding="utf-8").splitlines()):
        if len(row) == 3 and name in row[0]:
            cpu.append(float(row[1].rstrip("%")))
            mem.append(mib(row[2].split("/")[0]))
    return (statistics.median(cpu), max(cpu), max(mem)) if cpu else (0.0, 0.0, 0.0)


rows = []
for stats_file in sorted(OUT.glob("step_*_stats.csv"), key=lambda p: int(p.stem.split("_")[1])):
    users = int(stats_file.stem.split("_")[1])
    by_name = {r["Name"]: r for r in csv.DictReader(stats_file.open(encoding="utf-8"))}
    total = by_name["Aggregated"]
    requests, failures = int(total["Request Count"]), int(total["Failure Count"])
    api_cpu, api_cpu_max, api_mem = container_stats(users, "api")
    redis_cpu, _, _ = container_stats(users, "redis")
    docs = by_name.get("documents", {})
    sheet = by_name.get("spreadsheet", {})
    rows.append(
        f"| {users} | {requests} | {float(total['Requests/s']):.1f} | {total['50%']} | {total['95%']} "
        f"| {docs.get('50%', '-')} / {sheet.get('50%', '-')} | {100 * failures / max(requests, 1):.1f}% "
        f"| {api_cpu:.0f}% (max {api_cpu_max:.0f}%) | {api_mem:.0f} MiB | {redis_cpu:.1f}% |"
    )

table = "\n".join([
    "| Users | Requests | Req/s | p50 ms | p95 ms | p50 docs / sheet ms | Errors | API CPU (median) | API memory (max) | Redis CPU |",
    "|---|---|---|---|---|---|---|---|---|---|",
    *rows,
])
(OUT / "summary.md").write_text(table + "\n", encoding="utf-8")
print(table)
