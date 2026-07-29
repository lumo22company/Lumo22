#!/usr/bin/env python3
"""Run expanded LA aesthetics scrape across sub-areas and merge into one raw CSV."""

from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT / "exports"
TASK_ID = "KBdieEvDUh0rNaiw2"
DATE_SUFFIX = "2026-06-17"
OUT_CSV = EXPORTS_DIR / f"apify_raw_aesthetic_clinics_los_angeles_{DATE_SUFFIX}.csv"

LA_SUBAREAS = [
    "Beverly Hills, California, United States",
    "Santa Monica, California, United States",
    "West Hollywood, California, United States",
    "Downtown Los Angeles, California, United States",
    "Koreatown, Los Angeles, California, United States",
    "Pasadena, California, United States",
    "Glendale, California, United States",
    "Sherman Oaks, Los Angeles, California, United States",
    "Long Beach, California, United States",
    "Culver City, California, United States",
    "Burbank, California, United States",
    "Brentwood, Los Angeles, California, United States",
]

MAX_PER_SEARCH = 100
CHECKPOINT_PATH = EXPORTS_DIR / "la_expanded_scrape_checkpoint.json"


def _api(token: str, method: str, path: str, body: dict | None = None, retries: int = 5) -> dict | list:
    sep = "&" if "?" in path else "?"
    url = f"https://api.apify.com/v2{path}{sep}token={token}"
    data = json.dumps(body).encode() if body is not None else None
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
            if isinstance(payload, dict) and "data" in payload:
                return payload["data"]
            return payload
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429, 502, 503, 504) and attempt < retries:
                wait = 20 * attempt
                print(f"  API {e.code}, retry {attempt}/{retries - 1} in {wait}s...")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise SystemExit("API request failed")


def _load_checkpoint() -> tuple[dict[str, dict], set[str]]:
    if not CHECKPOINT_PATH.exists():
        return {}, set()
    data = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    merged = {k: v for k, v in data.get("merged", {}).items()}
    done = set(data.get("completed_areas", []))
    return merged, done


def _save_checkpoint(merged: dict[str, dict], completed_areas: set[str]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
        json.dumps(
            {
                "merged": merged,
                "completed_areas": sorted(completed_areas),
                "merged_total": len(merged),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _update_task_input(token: str, run_input: dict) -> None:
    task = _api(token, "GET", f"/actor-tasks/{TASK_ID}")
    if not isinstance(task, dict):
        raise SystemExit("Unexpected task payload")
    payload = {
        "actId": task["actId"],
        "name": task.get("name"),
        "title": task.get("title"),
        "options": task.get("options", {}),
        "input": run_input,
    }
    _api(token, "PUT", f"/actor-tasks/{TASK_ID}", payload)
    print(f"Updated task {TASK_ID} maxCrawledPlacesPerSearch={run_input.get('maxCrawledPlacesPerSearch')}")


def _wait_run(token: str, run_id: str, label: str) -> str:
    for i in range(180):
        data = _api(token, "GET", f"/actor-runs/{run_id}")
        if not isinstance(data, dict):
            raise SystemExit(f"Unexpected run payload for {label}")
        status = data.get("status")
        if i % 3 == 0:
            print(f"  [{label}] poll {i + 1}: {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            if status != "SUCCEEDED":
                raise SystemExit(f"Run failed ({label}): {status} {data.get('statusMessage')}")
            return str(data["defaultDatasetId"])
        time.sleep(20)
    raise SystemExit(f"Run timeout ({label})")


def _dataset_items(token: str, dataset_id: str) -> list[dict]:
    items: list[dict] = []
    offset = 0
    limit = 1000
    while True:
        path = f"/datasets/{dataset_id}/items?offset={offset}&limit={limit}&clean=1"
        batch = _api(token, "GET", path)
        if not batch:
            break
        if not isinstance(batch, list):
            raise SystemExit(f"Unexpected dataset payload for {dataset_id}")
        items.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return items


def main() -> None:
    load_dotenv(ROOT / ".env")
    token = os.getenv("APIFY_TOKEN", "").strip() or os.getenv("APIFY_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("APIFY_TOKEN missing")

    task = _api(token, "GET", f"/actor-tasks/{TASK_ID}")
    if not isinstance(task, dict):
        raise SystemExit("Unexpected task payload")
    base_input = dict(task["input"])
    base_input["maxCrawledPlacesPerSearch"] = MAX_PER_SEARCH
    _update_task_input(token, base_input)

    merged, completed = _load_checkpoint()
    per_area_counts: list[tuple[str, int]] = []

    for area in LA_SUBAREAS:
        if area in completed:
            print(f"\n=== Skipping completed area: {area} ===")
            continue
        label = area.split(",")[0]
        print(f"\n=== Starting scrape: {area} ===")
        run_input = dict(base_input)
        run_input["locationQuery"] = area
        _update_task_input(token, run_input)
        run = _api(token, "POST", f"/actor-tasks/{TASK_ID}/runs", {})
        if not isinstance(run, dict):
            raise SystemExit(f"Unexpected run create payload for {label}")
        dataset_id = _wait_run(token, run["id"], label)
        items = _dataset_items(token, dataset_id)
        added = 0
        for item in items:
            pid = (item.get("placeId") or "").strip()
            key = pid or f"{item.get('title','')}|{item.get('address','')}"
            if key not in merged:
                merged[key] = item
                added += 1
        completed.add(area)
        _save_checkpoint(merged, completed)
        per_area_counts.append((label, len(items)))
        print(f"  [{label}] fetched={len(items)} new_unique={added} merged_total={len(merged)}")
        time.sleep(15)

    if not merged:
        raise SystemExit("No rows merged")

    rows = list(merged.values())
    fieldnames: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    print("\n=== Expanded LA scrape complete ===")
    print(f"Sub-areas: {len(LA_SUBAREAS)}")
    print(f"maxCrawledPlacesPerSearch: {MAX_PER_SEARCH}")
    for label, count in per_area_counts:
        print(f"  {label}: {count}")
    print(f"Merged unique places: {len(rows)}")
    print(f"Wrote: {OUT_CSV}")


if __name__ == "__main__":
    main()
