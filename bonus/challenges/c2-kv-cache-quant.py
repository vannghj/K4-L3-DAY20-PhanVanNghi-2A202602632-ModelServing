#!/usr/bin/env python3
"""BONUS C2 - KV cache quantization: memory saved vs latency vs quality.

Runs llama-server three times with the same model and a large context, changing only
the KV cache data type (f16 -> q8_0 -> q4_0, both K and V, flash attention on for all
three so the comparison is fair). For each run it records:

  * KV cache size, parsed from the server log (what the cache type actually changes)
  * process RSS after load
  * prefill / decode speed on a ~4k-token prompt (where KV reads start to matter)
  * an auto-graded 10-prompt eval: arithmetic, JSON extraction, and needle-in-context
    retrieval from a long prompt (the case where a lossy KV cache should hurt first)

    .venv/bin/python bonus/challenges/c2-kv-cache-quant.py
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import subprocess
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))
import labkit  # noqa: E402

PORT = 8095
CTX = 32768
CONFIGS = ["f16", "q8_0", "q4_0"]

FILLER = (
    "The serving team reviewed dashboards, rotated on-call shifts, and wrote notes about "
    "queue depth, cache hit rates, and memory pressure on the inference fleet. "
)


def long_context(needle: str, position: float, sentences: int = 160) -> str:
    """~4k tokens of filler with one fact buried at `position` (0..1)."""
    body = [FILLER] * sentences
    body.insert(int(position * sentences), needle + " ")
    return "".join(body)


ARITH = [("Compute 37*24.", "888"), ("Compute 1234+5678.", "6912"),
         ("Compute 144/12.", "12"), ("Compute 99*99.", "9801")]
JSON_CASES = [
    ("Lan is 23 years old and lives in Hanoi.", {"name": "Lan", "age": 23, "city": "Hanoi"}),
    ("Minh, aged 41, works in Da Nang.", {"name": "Minh", "age": 41, "city": "Da Nang"}),
    ("Our customer Hoa (age 35) is based in Hue.", {"name": "Hoa", "age": 35, "city": "Hue"}),
]
NEEDLES = [("The vault access code is 4821.", "What is the vault access code?", "4821", 0.15),
           ("The backup server is named orion-7.", "What is the backup server named?", "orion-7", 0.5),
           ("The launch date was moved to March 19.", "What date was the launch moved to?", "19", 0.85)]


def ask(content: str, max_tokens: int = 64) -> tuple[str, dict]:
    r = httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                   json={"model": "local", "temperature": 0, "max_tokens": max_tokens,
                         "messages": [{"role": "user", "content": content}]},
                   timeout=600.0)
    r.raise_for_status()
    body = r.json()
    return body["choices"][0]["message"]["content"] or "", body.get("timings") or {}


def grade_json(text: str, want: dict) -> bool:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return False
    try:
        got = json.loads(m.group())
    except ValueError:
        return False
    return (str(got.get("name", "")).strip() == want["name"]
            and str(got.get("age", "")).strip() == str(want["age"])
            and str(got.get("city", "")).strip() == want["city"])


def run_eval() -> tuple[int, list[str]]:
    passed, fails = 0, []
    for q, ans in ARITH:
        text, _ = ask(f"{q} Answer with only the number.")
        ok = ans in text.replace(",", "")
        passed += ok
        if not ok:
            fails.append(f"arith `{q}` -> `{text.strip()[:40]}`")
    for src, want in JSON_CASES:
        text, _ = ask("Extract the person's name, age and city as JSON with keys "
                      f"name, age (integer), city. Output only JSON.\n\n{src}", 96)
        ok = grade_json(text, want)
        passed += ok
        if not ok:
            fails.append(f"json `{src[:30]}...` -> `{text.strip()[:60]}`")
    for needle, q, ans, pos in NEEDLES:
        text, _ = ask(f"{long_context(needle, pos)}\n\nQuestion: {q} Answer briefly.")
        ok = ans.lower() in text.lower()
        passed += ok
        if not ok:
            fails.append(f"needle@{pos:.0%} `{q}` -> `{text.strip()[:50]}`")
    return passed, fails


def speed() -> dict:
    """Prefill + decode on a ~4k-token prompt, 3 reps, median."""
    pp, tg = [], []
    for i in range(3):
        prompt = f"Run {i}. " + long_context("Note: nothing special here.", 0.5)
        _, t = ask(prompt + "\n\nSummarise the notes above in five sentences.", 128)
        if t.get("prompt_per_second"):
            pp.append(t["prompt_per_second"])
        if t.get("predicted_per_second"):
            tg.append(t["predicted_per_second"])
    return {"prompt_n": t.get("prompt_n"),
            "pp_tok_s": statistics.median(pp) if pp else 0.0,
            "tg_tok_s": statistics.median(tg) if tg else 0.0}


def rss_mb(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    return int(out.stdout.strip() or 0) / 1024


def kv_size(log: str) -> str:
    m = re.findall(r"llama_kv_cache: size\s*=\s*([\d.]+)\s*MiB", log)
    return m[-1] if m else "?"


def main() -> int:
    model = str(labkit.repo_root() / labkit.load_active()["primary_model"])
    log_path = labkit.bench_dir() / ".c2-server.log"
    rows = []
    for ct in CONFIGS:
        labkit.banner(f"KV cache type {ct}")
        cmd = labkit.server_cmd(model, port=PORT, extra=[
            "-fa", "on", "-ctk", ct, "-ctv", ct, "--ctx-size", str(CTX), "--parallel", "1", "-lv", "4"])
        with open(log_path, "w") as fh:
            proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT)
        try:
            if not labkit.wait_healthy(PORT, proc=proc):
                print(log_path.read_text()[-2000:])
                labkit.die(f"server with -ctk {ct} did not start")
            ask("Hello.", 8)                                   # warm-up
            rss = rss_mb(proc.pid)
            kv = kv_size(log_path.read_text())
            sp = speed()
            passed, fails = run_eval()
        finally:
            proc.terminate()
            proc.wait(timeout=30)
        kv_lines = [l.strip() for l in log_path.read_text().splitlines()
                    if re.search(r"(llama_kv_cache|llama_memory_recurrent): size", l)]
        row = {"type": ct, "kv_mib": kv, "rss_mb": round(rss), **sp,
               "passed": passed, "fails": fails, "kv_log": kv_lines}
        rows.append(row)
        print(json.dumps(row, indent=1))

    table = labkit.md_table(
        ["KV type (K+V)", "KV cache (MiB)", "RSS (MB)", "Prefill ~4k tok (tok/s)",
         "Decode (tok/s)", "Eval (/10)"],
        [[r["type"], r["kv_mib"], r["rss_mb"], f"{r['pp_tok_s']:.0f}", f"{r['tg_tok_s']:.1f}",
          r["passed"]] for r in rows])
    fails = "\n".join(f"- `{r['type']}`: " + ("; ".join(r["fails"]) or "none") for r in rows)
    logs = "\n".join(f"{r['type']}:\n" + "\n".join(f"    {l}" for l in r["kv_log"]) for r in rows)
    md = f"""# Bonus C2 - KV cache quantization

Model `{pathlib.Path(model).name}` · llama.cpp `{labkit.LLAMA_CPP_BUILD}` · `ngl={labkit.n_gpu_layers()}`
`--ctx-size {CTX}` · `--parallel 1` · `-fa on` for every row · temperature 0 ·
speed = median of 3 runs on a {rows[0].get('prompt_n')}-token prompt

{table}

Eval = 4 arithmetic + 3 JSON extraction + 3 needle-in-a-~4k-token-context, auto-graded.

Failures:
{fails}

KV cache lines from the server log:

```
{logs}
```

## Your explanation (required -- replace this line)
"""
    out = labkit.write_report("bonus-c2-kv-cache.md", md, rows)
    print(md)
    print(f"==> Wrote {out.relative_to(labkit.repo_root())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
