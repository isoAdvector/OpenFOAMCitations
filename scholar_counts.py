#!/usr/bin/env python3
"""
Collect Google Scholar approximate result counts for "OpenFOAM"
for each year 2005–<current_year>. All years are re-fetched every run.
"""

import re
import time
import random
import csv
import sys
from typing import Optional, Tuple, List
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import matplotlib.pyplot as plt

SEARCH_URL = "https://scholar.google.com/scholar"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

PARAMS_BASE = {
    "as_q": "OpenFOAM",
    "hl": "en",
    "as_sdt": "0,5",
}

_PATTERNS = [
    re.compile(r"About\s+([\d\s.,\u00A0]+)\s+results", re.IGNORECASE),
    re.compile(r"of about\s+([\d\s.,\u00A0]+)\s+results", re.IGNORECASE),
    re.compile(r"^\s*([\d\s.,\u00A0]+)\s+results", re.IGNORECASE | re.MULTILINE),
]


def requests_session_with_retries() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _strip_to_int(num_str: str) -> Optional[int]:
    digits_only = re.sub(r"[^\d]", "", num_str)
    return int(digits_only) if digits_only else None


def parse_results_count(html: str) -> Optional[int]:
    lower = html.lower()
    if "unusual traffic" in lower or "recaptcha" in lower:
        return None
    if "did not match any articles" in lower:
        return 0
    for pat in _PATTERNS:
        m = pat.search(html)
        if m:
            return _strip_to_int(m.group(1))
    return None


def fetch_year_count(session: requests.Session, year: int, max_attempts: int = 3) -> Tuple[int, Optional[int], Optional[str]]:
    params = dict(PARAMS_BASE)
    params["as_ylo"] = str(year)
    params["as_yhi"] = str(year)

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(SEARCH_URL, headers=HEADERS, params=params, timeout=30)
            if resp.status_code in (429, 503):
                last_err = f"HTTP {resp.status_code}"
                time.sleep(2 * attempt + random.uniform(0.0, 1.0))
                continue
            count = parse_results_count(resp.text)
            if count is not None:
                return year, count, None
            last_err = "Could not parse results count (possible block or page variant)"
        except requests.RequestException as e:
            last_err = f"Request error: {e}"
        time.sleep(1.5 * attempt + random.uniform(0.0, 0.6))
    return year, None, last_err


def main():
    start_year = 2005
    end_year = datetime.now().year  # current year

    out_csv = f"openfoam_scholar_counts_{start_year}_{end_year}.csv"
    out_png = "openfoam_trend.png"

    years = list(range(start_year, end_year + 1))

    results: List[Tuple[int, int]] = []
    session = requests_session_with_retries()

    print(f"Collecting Google Scholar counts for 'OpenFOAM' ({start_year}–{end_year})...")
    for i, y in enumerate(years, 1):
        if i > 1:
            time.sleep(random.uniform(2.0, 4.0))

        year, count, err = fetch_year_count(session, y)
        if err:
            print(f"{year}: ERROR - {err}")
            count = 0
        else:
            print(f"{year}: {count} results")
        results.append((year, count))

    # Save CSV
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "approx_results"])
        writer.writerows(results)
    print(f"Saved CSV -> {out_csv}")

    years_plot = [y for y, _ in results]
    counts_plot = [c for _, c in results]


    # Bar plot
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(years_plot, counts_plot, color="skyblue", edgecolor="black")
    ax.set_title(f'Google Scholar "OpenFOAM" approximate results by year ({start_year}–{end_year})')
    ax.set_xlabel("Year")
    ax.set_ylabel("Approximate results")
    ax.set_xticks(years_plot)
    ax.set_xticklabels(years_plot, rotation=45)
    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.6)

    # Annotation in top-left corner inside axes
    updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    footer = f"Last updated: {updated}\nPlot provided by Johan Roenby, STROMNING"
    ax.text(
        0.01, 0.97, footer,
        transform=ax.transAxes,
        ha="left", va="top",
        fontsize=9, style="italic",
        bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=2)
    )

    fig.tight_layout()
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    print(f"Saved bar plot -> {out_png}")
    plt.show()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
