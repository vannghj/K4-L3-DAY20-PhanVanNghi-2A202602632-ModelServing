#!/usr/bin/env python3
"""B1 follow-up: is the prebuilt-vs-source gap bigger than run-to-run noise?

`make compare-builds` runs each binary once, back to back. On a laptop that is also
running an editor, one pass can drift by ~10%, so this interleaves the two binaries
for several rounds (prebuilt, source, prebuilt, source, ...) on both decode (tg128)
and prefill (pp512), CPU only (-ngl 0, -t 4), and reports mean and spread.

    .venv/bin/python bonus/challenges/b1-interleaved.py --rounds 5
"""
from __future__ import annotations

import argparse
import csv
import io
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))
import labkit  # noqa: E402

ROOT = labkit.repo_root()


def bench(binary: pathlib.Path, model: str, threads: int) -> dict[str, float]:
    out = subprocess.run(
        [str(binary), "-m", model, "-t", str(threads), "-ngl", "0",
         "-p", "512", "-n", "128", "-r", "3", "-o", "csv"],
        capture_output=True, text=True, check=True, timeout=900).stdout
    res = {}
    for row in csv.DictReader(io.StringIO(out)):
        key = "pp512" if row["n_prompt"] == "512" else "tg128"
        res[key] = float(row["avg_ts"])
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    model = str(ROOT / labkit.load_active()["primary_model"])
    bins = {"prebuilt": next(sorted((ROOT / "runtime").rglob("llama-bench")).__iter__()),
            "source": labkit.source_build_bin("llama-bench")}
    runs: dict[str, dict[str, list[float]]] = {b: {"pp512": [], "tg128": []} for b in bins}
    for r in range(1, args.rounds + 1):
        for name, binary in bins.items():
            res = bench(binary, model, args.threads)
            for k, v in res.items():
                runs[name][k].append(v)
            print(f"round {r}  {name:8s}  pp512 {res['pp512']:7.1f}  tg128 {res['tg128']:6.1f}",
                  flush=True)

    rows = []
    for metric in ("pp512", "tg128"):
        a, b = runs["prebuilt"][metric], runs["source"][metric]
        ma, mb = statistics.mean(a), statistics.mean(b)
        rows.append([metric,
                     f"{ma:.1f} ± {statistics.stdev(a):.1f}", f"{min(a):.1f}–{max(a):.1f}",
                     f"{mb:.1f} ± {statistics.stdev(b):.1f}", f"{min(b):.1f}–{max(b):.1f}",
                     f"{mb / ma:.2f}x"])
    table = labkit.md_table(
        ["metric", "prebuilt mean ± sd", "prebuilt range", "source mean ± sd", "source range",
         "source / prebuilt"], rows)
    raw = "\n".join(
        f"| {i + 1} | {runs['prebuilt']['pp512'][i]:.1f} | {runs['source']['pp512'][i]:.1f} | "
        f"{runs['prebuilt']['tg128'][i]:.1f} | {runs['source']['tg128'][i]:.1f} |"
        for i in range(args.rounds))
    md = f"""# Bonus B1 follow-up - interleaved prebuilt vs source build

`{pathlib.Path(model).name}` · CPU only (`-ngl 0`) · `-t {args.threads}` · {args.rounds} rounds,
binaries alternated each round, each point = llama-bench `-r 3` average

{table}

| round | prebuilt pp512 | source pp512 | prebuilt tg128 | source tg128 |
|--:|--:|--:|--:|--:|
{raw}
"""
    out = labkit.write_report("bonus-b1-interleaved.md", md, runs)
    print(md)
    print(f"==> Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
