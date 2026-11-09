"""
Build an analysis-ready subset of trailer_stats.csv.

    trailer_stats.csv --filter (year >= 2008, status == "ok")-->
        + IMDb rating / votes      (from input/IMDbmovies250.csv)
        + release date, budget, revenue   (TMDB /movie/{id}, cached per movie)
        + derived columns (upload lag, likes per view / per day, ROI)
    --> output/analysis_subset.csv

Read-only inputs: output/trailer_stats.csv, everything in input/, and the
existing caches in raw/tmdb/ and raw/youtube/. The only new files are
raw/tmdb_details/{imdb_id}.json (one per movie, skipped on rerun) and the
output CSV. YouTube is never called: publish dates come from the cache.

Usage (from the repo root):
    python pipeline/build_subset.py
"""

import csv
import json
import logging
import os
import statistics
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

# Reuse the HTTP helpers from the fetch script: retry with backoff, and
# error messages that never contain the API key.
from fetch_trailers import (
    APIError, INPUT_CSV, REPO_ROOT, TMDB_BASE, TMDB_CACHE, YT_CACHE,
    get_json, load_youtube_cache, tmdb_auth, write_atomic,
)

PIPELINE_DIR = Path(__file__).resolve().parent
TRAILER_CSV = PIPELINE_DIR / "output" / "trailer_stats.csv"  # read-only
SUBSET_CSV = PIPELINE_DIR / "output" / "analysis_subset.csv"
DETAILS_CACHE = PIPELINE_DIR / "raw" / "tmdb_details"  # new; raw/tmdb is left alone

MIN_YEAR = 2008
NEAR_RELEASE_DAYS = 365  # trailer_near_release: |upload_lag_days| <= this

NEW_COLUMNS = [
    "tmdb_id", "release_date", "budget", "revenue", "roi",
    "imdb_rating", "imdb_votes",
    "upload_lag_days", "trailer_near_release",
    "stats_pulled_on",
    "days_online", "primary_likes_per_view", "primary_likes_per_day",
    "most_viewed_published_at", "most_viewed_days_online",
    "most_viewed_likes_per_view", "most_viewed_likes_per_day",
]

log = logging.getLogger("build_subset")


# --- Small parsing helpers (blank or bad input -> None, never a crash) ------

def to_num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_date(value):
    """Parse '2010-02-19' or YouTube's '2009-11-05T18:30:00Z' to a date."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def ratio(numerator, denominator, digits):
    """numerator / denominator, or None if either is missing or the
    denominator is zero."""
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator, digits)


def positive_or_none(value):
    """TMDB reports unknown budget/revenue as 0. Treat 0 as missing."""
    return value if value else None


def fmt(value):
    """CSV cell: None -> '', bools -> 'true'/'false', whole floats -> ints."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# --- Data sources -----------------------------------------------------------

def load_ratings():
    """{imdb_id: (rating, votes)} from the IMDb input file."""
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        return {r["id"].strip(): (to_num(r["averageRating"]), to_num(r["numVotes"]))
                for r in csv.DictReader(f)}


def cached_tmdb_id(imdb_id):
    """TMDB id from the /find response that fetch_trailers.py already cached."""
    path = TMDB_CACHE / f"{imdb_id}.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    results = (record.get("find") or {}).get("movie_results") or []
    return results[0].get("id") if results else None


def fetch_details(imdb_id, tmdb_id, auth_params, auth_headers):
    """TMDB /movie/{id} response, from raw/tmdb_details/ if already cached."""
    path = DETAILS_CACHE / f"{imdb_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    details = get_json(f"{TMDB_BASE}/movie/{tmdb_id}", params=auth_params,
                       headers=auth_headers, label=f"TMDB details {imdb_id}")
    write_atomic(path, json.dumps(details, indent=2))
    return details


def stats_pull_date():
    """The date the YouTube stats were fetched, which is the newest batch
    file's modification date. Using this instead of today's date keeps
    days_online (and so likes-per-day) correct when the script is rerun
    later without re-fetching the stats."""
    batches = list(YT_CACHE.glob("batch_*.json"))
    if not batches:
        return date.today()
    newest = max(p.stat().st_mtime for p in batches)
    return datetime.fromtimestamp(newest).date()


# --- Building the subset ----------------------------------------------------

def filter_rows(rows):
    """Apply the subset filter, printing what each step removes."""
    print(f"trailer_stats.csv: {len(rows)} rows")

    recent = [r for r in rows if (to_num(r["year"]) or 0) >= MIN_YEAR]
    print(f"  year >= {MIN_YEAR}:     removes {len(rows) - len(recent):3d} -> {len(recent)} left")

    kept = [r for r in recent if r["status"] == "ok" and r["primary_likes"] != ""]
    dropped = [r for r in recent if r not in kept]
    print(f"  status == ok:    removes {len(dropped):3d} -> {len(kept)} left")
    print(f"    by status: {dict(Counter(r['status'] for r in dropped))}")
    for r in dropped:
        print(f"    - {r['imdb_id']}  {r['year']}  {r['title']}  ({r['status']})")
    return kept


def add_columns(row, ratings, details, yt_items, pulled_on):
    """Return the new columns for one movie as {name: value}."""
    new = dict.fromkeys(NEW_COLUMNS)
    new["stats_pulled_on"] = pulled_on.isoformat()

    rating, votes = ratings.get(row["imdb_id"], (None, None))
    new["imdb_rating"], new["imdb_votes"] = rating, votes

    # TMDB fields. details is {} if the movie had no TMDB match or the call failed.
    release = to_date(details.get("release_date"))
    budget = positive_or_none(details.get("budget"))
    revenue = positive_or_none(details.get("revenue"))
    new.update(tmdb_id=details.get("id"),
               release_date=release.isoformat() if release else None,
               budget=budget, revenue=revenue,
               roi=ratio(revenue, budget, 3))

    # Primary trailer. Negative lag means it went up before the film's release.
    published = to_date(row["primary_published_at"])
    if published and release:
        lag = (published - release).days
        new["upload_lag_days"] = lag
        new["trailer_near_release"] = abs(lag) <= NEAR_RELEASE_DAYS
    if published:
        new["days_online"] = (pulled_on - published).days
    views, likes = to_num(row["primary_views"]), to_num(row["primary_likes"])
    new["primary_likes_per_view"] = ratio(likes, views, 6)
    new["primary_likes_per_day"] = ratio(likes, new["days_online"], 2)

    # Most-viewed trailer: trailer_stats.csv doesn't store its publish date,
    # so look it up in the cached YouTube responses.
    item = yt_items.get(row["most_viewed_video_id"]) or {}
    mv_published = to_date((item.get("snippet") or {}).get("publishedAt"))
    if mv_published:
        new["most_viewed_published_at"] = item["snippet"]["publishedAt"]
        new["most_viewed_days_online"] = (pulled_on - mv_published).days
    mv_views, mv_likes = to_num(row["most_viewed_views"]), to_num(row["most_viewed_likes"])
    new["most_viewed_likes_per_view"] = ratio(mv_likes, mv_views, 6)
    new["most_viewed_likes_per_day"] = ratio(mv_likes, new["most_viewed_days_online"], 2)
    return new


def print_summary(out_rows):
    def count(col):
        return sum(1 for r in out_rows if r[col] != "")

    lags = [int(r["upload_lag_days"]) for r in out_rows if r["upload_lag_days"] != ""]
    near = sum(1 for r in out_rows if r["trailer_near_release"] == "true")
    print(f"\nWrote {SUBSET_CSV.relative_to(REPO_ROOT)}")
    print(f"  rows:                        {len(out_rows)}")
    print(f"  with revenue:                {count('revenue')}")
    print(f"  with budget:                 {count('budget')}")
    print(f"  with imdb_rating:            {count('imdb_rating')}")
    print(f"  trailer_near_release = true: {near}")
    print(f"  median upload_lag_days:      {statistics.median(lags) if lags else 'n/a'}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    load_dotenv(REPO_ROOT / ".env")
    tmdb_key = os.getenv("TMDB_API_KEY")
    if not tmdb_key:
        log.error("TMDB_API_KEY is missing from %s", REPO_ROOT / ".env")
        return 1
    auth_params, auth_headers = tmdb_auth(tmdb_key)
    DETAILS_CACHE.mkdir(parents=True, exist_ok=True)

    with TRAILER_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        original_columns = reader.fieldnames
        rows = list(reader)
    subset = filter_rows(rows)

    ratings = load_ratings()
    yt_items, _ = load_youtube_cache()
    pulled_on = stats_pull_date()

    out_rows = []
    for row in subset:
        imdb_id = row["imdb_id"]
        details = {}
        tmdb_id = cached_tmdb_id(imdb_id)
        if tmdb_id is None:
            log.warning("%s: no TMDB match in cache; TMDB columns left empty", imdb_id)
        else:
            try:
                details = fetch_details(imdb_id, tmdb_id, auth_params, auth_headers)
            except APIError as e:
                if e.status == 401:  # wrong key: every other call would fail too
                    log.error("TMDB rejected the API key (HTTP 401). Check TMDB_API_KEY.")
                    return 1
                log.warning("%s (TMDB columns left empty; rerun to retry)", e)
        new = add_columns(row, ratings, details, yt_items, pulled_on)
        out_rows.append({**row, **{k: fmt(v) for k, v in new.items()}})

    SUBSET_CSV.parent.mkdir(parents=True, exist_ok=True)
    tmp = SUBSET_CSV.with_name(SUBSET_CSV.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=original_columns + NEW_COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)
    os.replace(tmp, SUBSET_CSV)

    print_summary(out_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
