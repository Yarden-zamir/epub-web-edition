# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Run Lighthouse on the web edition: the home page and a long chapter deep link, on mobile and desktop.

Usage, from the repo root:
  uv run books/eli-raz/scripts/lighthouse.py OUT_DIR NAME=SITE [NAME=SITE ...]

SITE is a web folder (served with `serve`, which compresses with gzip) or an http(s) address, for example
  main=/tmp/base/books/eli-raz/dist/release/web pr=books/eli-raz/dist/release/web
  live=https://eli-raz.yarden-zamir.com

Runners differ in speed by up to 2x, so compare sites only within one run: the runs of all sites take turns.
Each page and device runs RUNS times per site; the run with the median Performance score is kept as
OUT_DIR/<name>-<page>-<device>.report.{html,json}. Prints a Markdown summary (scores, LCP, CLS, TBT, total bytes,
audits below 0.9) and appends it to $GITHUB_STEP_SUMMARY when that is set.
Needs `lighthouse` (13.6.0) and `serve` (14.2.7) on PATH and a Chrome that Lighthouse finds.
Exit code 0 when every run produced a report. Low scores do not fail the run: .github/workflows/lighthouse.yml is
advisory.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PAGES = {"home": "/", "chapter": "/#a34"}  # a34 is the longest chapter, near the end of the page.
DEVICES = ["mobile", "desktop"]
RUNS = 3
FIRST_PORT = 8080
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
METRICS = {
    "largest-contentful-paint": "LCP",
    "cumulative-layout-shift": "CLS",
    "total-blocking-time": "TBT",
    "total-byte-weight": "bytes",
}

type Key = tuple[str, str, str]  # Site name, page, device.


def wait_for(url: str) -> None:
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"server at {url} did not start")


def lighthouse(url: str, device: str, out_base: Path) -> dict:
    cmd = [
        "lighthouse", url, "--quiet", "--output=json", "--output=html", f"--output-path={out_base}",
        "--chrome-flags=--headless=new --no-sandbox",
    ]
    if device == "desktop":
        cmd.append("--preset=desktop")
    subprocess.run(cmd, check=True)
    return json.loads(out_base.with_suffix(".report.json").read_text(encoding="utf-8"))


def score(report: dict, category: str) -> int:
    value = report["categories"][category]["score"]
    if value is None:
        raise SystemExit(f"no {category} score in the report of {report['finalDisplayedUrl']}")
    return round(value * 100)


def failing_audits(report: dict) -> list[str]:
    lines = []
    for category in CATEGORIES:
        for ref in report["categories"][category]["auditRefs"]:
            audit = report["audits"][ref["id"]]
            if ref["weight"] > 0 and audit["score"] is not None and audit["score"] < 0.9:
                shown = audit.get("displayValue", "")
                lines.append(f"{category}: {audit['id']} ({audit['score']:.2f}) {shown}".rstrip())
    return lines


def summary(results: dict[Key, dict]) -> str:
    head = ["page", "device", "site", "Perf", "A11y", "BP", "SEO", *METRICS.values(), "CPU index"]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    details = []
    for key in sorted(results, key=lambda k: (k[1], k[2])):  # Sites of one page and device side by side.
        name, page, device = key
        report = results[key]
        metrics = [report["audits"][m]["displayValue"].removeprefix("Total size was ") for m in METRICS]
        scores = [str(score(report, c)) for c in CATEGORIES]
        cpu = str(round(report["environment"]["benchmarkIndex"]))
        rows.append("| " + " | ".join([page, device, name, *scores, *metrics, cpu]) + " |")
        details += [f"<details><summary>{name} {page} {device}: audits below 0.9</summary>", "", "```"]
        details += failing_audits(report) or ["none"]
        details += ["```", "</details>"]
    return "\n".join(["### Lighthouse (median of 3)", "", *rows, "", *details, ""])


def main() -> None:
    if len(sys.argv) < 3 or any("=" not in a for a in sys.argv[2:]):
        raise SystemExit(__doc__)
    out_dir = Path(sys.argv[1])
    sites = dict(a.split("=", 1) for a in sys.argv[2:])
    if len(sites) != len(sys.argv) - 2:
        raise SystemExit("each site name must be unique")
    for tool in ["lighthouse", "serve"]:
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is not on PATH")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)

    servers = []
    bases: dict[str, str] = {}
    try:
        for port, (name, site) in enumerate(sites.items(), FIRST_PORT):
            if site.startswith(("http://", "https://")):
                bases[name] = site.rstrip("/")
                continue
            if not (Path(site) / "index.html").is_file():
                raise SystemExit(f"{name}: no index.html in {site}")
            servers.append(subprocess.Popen(["serve", "--no-port-switching", "-l", str(port), site]))
            bases[name] = f"http://localhost:{port}"
            wait_for(bases[name] + "/")
        runs: dict[Key, list[tuple[dict, Path]]] = {}
        for page, path in PAGES.items():
            for device in DEVICES:
                for n in range(RUNS):
                    for name, base in bases.items():  # Sites take turns, so a slow minute hits all of them.
                        out_base = out_dir / "runs" / f"{name}-{page}-{device}-{n}"
                        report = lighthouse(base + path, device, out_base)
                        runs.setdefault((name, page, device), []).append((report, out_base))
    finally:
        for server in servers:
            server.terminate()

    results: dict[Key, dict] = {}
    for key, reports in runs.items():
        reports.sort(key=lambda r: score(r[0], "performance"))
        report, out_base = reports[len(reports) // 2]
        for suffix in [".report.json", ".report.html"]:
            shutil.copy(out_base.with_suffix(suffix), out_dir / ("-".join(key) + suffix))
        results[key] = report

    text = summary(results)
    print(text)
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
