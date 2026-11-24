# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Run Lighthouse on the web edition: the home page and a long chapter deep link, on mobile and desktop.

Usage, from the repo root:
  uv run books/eli-raz/scripts/lighthouse.py WEB_DIR OUT_DIR      serve WEB_DIR with `serve` (gzip) and measure it
  uv run books/eli-raz/scripts/lighthouse.py --url URL OUT_DIR    measure a live site, for example the deployed one

Needs `lighthouse` (13.6.0) and `serve` (14.2.7) on PATH and a Chrome that Lighthouse finds. Each page and device
runs RUNS times; the run with the median Performance score is kept as <page>-<device>.report.{html,json} in OUT_DIR.
Prints a Markdown summary (scores, LCP, CLS, TBT, total bytes, audits that fail) and appends it to
$GITHUB_STEP_SUMMARY when that is set. Exit code 0 when every run produced a report, 1 otherwise. Low scores do not
fail the run: .github/workflows/lighthouse.yml is advisory.
"""

import argparse
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
PORT = 8080
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
METRICS = {
    "largest-contentful-paint": "LCP",
    "cumulative-layout-shift": "CLS",
    "total-blocking-time": "TBT",
    "total-byte-weight": "bytes",
}


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


def summary(results: dict[tuple[str, str], dict]) -> str:
    head = ["page", "device", "Perf", "A11y", "BP", "SEO", *METRICS.values()]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for (page, device), report in results.items():
        metrics = [report["audits"][m]["displayValue"] for m in METRICS]
        scores = [str(score(report, c)) for c in CATEGORIES]
        rows.append("| " + " | ".join([page, device, *scores, *metrics]) + " |")
    details = []
    for (page, device), report in results.items():
        details += [f"<details><summary>{page} {device}: audits below 0.9</summary>", "", "```"]
        details += failing_audits(report) or ["none"]
        details += ["```", "</details>"]
    return "\n".join(["### Lighthouse", "", *rows, "", *details, ""])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("web_dir", nargs="?", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--url", help="measure this site instead of serving WEB_DIR")
    args = parser.parse_args()
    if (args.url is None) == (args.web_dir is None):
        parser.error("give WEB_DIR or --url, not both")
    for tool in ["lighthouse", "serve"]:
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is not on PATH")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    server = None
    base = args.url.rstrip("/") if args.url else f"http://localhost:{PORT}"
    if args.web_dir:
        if not (args.web_dir / "index.html").is_file():
            raise SystemExit(f"no index.html in {args.web_dir}")
        server = subprocess.Popen(["serve", "--no-port-switching", "-l", str(PORT), str(args.web_dir)])
        wait_for(base + "/")
    try:
        results = {}
        for page, path in PAGES.items():
            for device in DEVICES:
                runs = []
                for n in range(RUNS):
                    out_base = args.out_dir / "runs" / f"{page}-{device}-{n}"
                    out_base.parent.mkdir(exist_ok=True)
                    runs.append((lighthouse(base + path, device, out_base), out_base))
                runs.sort(key=lambda r: score(r[0], "performance"))
                report, out_base = runs[len(runs) // 2]
                for suffix in [".report.json", ".report.html"]:
                    shutil.copy(out_base.with_suffix(suffix), args.out_dir / f"{page}-{device}{suffix}")
                results[(page, device)] = report
    finally:
        if server:
            server.terminate()

    text = summary(results)
    print(text)
    if step_summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    sys.exit(main())
