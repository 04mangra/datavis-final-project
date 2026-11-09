"""
Fetch official YouTube trailer stats for each movie in the IMDb top 250.

    IMDb ID --TMDB /find--> TMDB ID --TMDB /videos--> YouTube video IDs
            --YouTube videos.list (50 per call)--> views / likes / comments

Every raw API response is cached under pipeline/raw/ and nothing cached is
ever requested again, so the script can be stopped, crash, or hit the quota at
any point. Just rerun it to pick up where it left off.

Usage (from the repo root):
    pip install -r pipeline/requirements.txt
    python pipeline/fetch_trailers.py
"""

import csv
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
INPUT_CSV = PIPELINE_DIR / "input" / "IMDbmovies250.csv"  # read-only
OUTPUT_CSV = PIPELINE_DIR / "output" / "trailer_stats.csv"
TMDB_CACHE = PIPELINE_DIR / "raw" / "tmdb"
YT_CACHE = PIPELINE_DIR / "raw" / "youtube"

TMDB_BASE = "https://api.themoviedb.org/3"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YT_BATCH_SIZE = 50  # max IDs videos.list accepts per call (1 quota unit each)
MAX_ATTEMPTS = 5
RETRY_STATUSES = {429, 500, 502, 503, 504}

OUTPUT_COLUMNS = [
    "imdb_id", "title", "year",
    "primary_video_id", "primary_views", "primary_likes", "primary_comments",
    "primary_published_at", "primary_channel",
    "most_viewed_video_id", "most_viewed_views", "most_viewed_likes",
    "num_candidates",
    "tmdb_title", "primary_video_title",  # extras, handy for sanity checks
    "status",
]

log = logging.getLogger("fetch_trailers")
session = requests.Session()


class APIError(Exception):
    """A request failed in a way retrying won't fix (or retries ran out)."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class QuotaExceeded(Exception):
    """YouTube daily quota is used up. Stop now and rerun after it resets."""


# --- HTTP helpers -----------------------------------------------------------

def is_youtube_quota_error(resp):
    """YouTube signals quota exhaustion as a 403 with a specific 'reason'."""
    try:
        reasons = {e.get("reason") for e in resp.json()["error"]["errors"]}
    except (ValueError, KeyError, TypeError):
        return False
    return bool(reasons & {"quotaExceeded", "dailyLimitExceeded"})


def get_json(url, params=None, headers=None, label="request"):
    """GET and return parsed JSON, retrying transient failures with backoff.

    Messages never include the URL, params, or str(exception), because
    those can contain the API key.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        retry_after = None
        try:
            resp = session.get(url, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            problem = type(e).__name__
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403 and is_youtube_quota_error(resp):
                raise QuotaExceeded()
            if resp.status_code not in RETRY_STATUSES:
                raise APIError(f"{label}: HTTP {resp.status_code}", resp.status_code)
            problem = f"HTTP {resp.status_code}"
            retry_after = resp.headers.get("Retry-After")

        if attempt == MAX_ATTEMPTS:
            break
        # Honour the server's Retry-After on 429s, otherwise back off 2, 4, 8, 16s.
        wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
        log.warning("%s failed (%s); retry %d/%d in %ds",
                    label, problem, attempt, MAX_ATTEMPTS - 1, wait)
        time.sleep(wait)
    raise APIError(f"{label}: still failing after {MAX_ATTEMPTS} attempts ({problem})")


def tmdb_auth(key):
    """Return (query params, headers) for TMDB.

    TMDB issues two credential types: a short v3 "API key" sent as a query
    param, and a long v4 "read access token" (a JWT, starts with 'eyJ') sent
    as a Bearer header. Accept either.
    """
    if key.startswith("eyJ"):
        return {}, {"Authorization": f"Bearer {key}"}
    return {"api_key": key}, {}


def write_atomic(path, text):
    """Write to a temp file, then rename. If the script crashes mid-write,
    there's no half-written file to be mistaken for a complete one."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# --- Stage 1: TMDB (one cache file per movie) -------------------------------

def fetch_tmdb(imdb_id, auth_params, auth_headers):
    """Return {"find": ..., "videos": ...} for one movie, from cache if present."""
    path = TMDB_CACHE / f"{imdb_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    find = get_json(f"{TMDB_BASE}/find/{imdb_id}",
                    params={**auth_params, "external_source": "imdb_id"},
                    headers=auth_headers, label=f"TMDB find {imdb_id}")
    matches = find.get("movie_results") or []
    videos = None
    if matches:
        # Note: TMDB defaults to en-US here, so non-English-only trailers are excluded.
        videos = get_json(f"{TMDB_BASE}/movie/{matches[0]['id']}/videos",
                          params=auth_params, headers=auth_headers,
                          label=f"TMDB videos {imdb_id}")

    # Cache only once both calls succeed, so a failed movie is retried next run.
    record = {"find": find, "videos": videos}
    write_atomic(path, json.dumps(record, indent=2))
    return record


def trailer_candidates(record):
    """Return (official YouTube trailer IDs, count of unofficial ones)."""
    results = (record.get("videos") or {}).get("results") or []
    trailers = [v for v in results
                if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
    # dict.fromkeys drops duplicate keys while keeping order.
    official = list(dict.fromkeys(v["key"] for v in trailers if v.get("official") is True))
    return official, sum(1 for v in trailers if v.get("official") is not True)


# --- Stage 2: YouTube (one cache file per batch) ----------------------------

def load_youtube_cache():
    """Return (video items by ID, set of every ID ever requested)."""
    items, requested = {}, set()
    for path in sorted(YT_CACHE.glob("batch_*.json")):
        batch = json.loads(path.read_text(encoding="utf-8"))
        requested.update(batch["requested_ids"])
        for item in batch["response"].get("items", []):
            items[item["id"]] = item
    return items, requested


def fetch_youtube(video_ids, api_key):
    """Fetch stats for any video IDs not already cached; return all items by ID."""
    items, requested = load_youtube_cache()
    # Each batch file stores the IDs it *asked* for, not just the ones YouTube
    # returned. So deleted/private videos count as done and aren't re-bought on
    # every run, and the batch boundaries don't need to be reproducible.
    todo = sorted(set(video_ids) - requested)
    batches = [todo[i:i + YT_BATCH_SIZE] for i in range(0, len(todo), YT_BATCH_SIZE)]
    log.info("YouTube: %d videos cached, %d to fetch in %d batch(es)",
             len(requested & set(video_ids)), len(todo), len(batches))

    existing = [int(p.stem.split("_")[1]) for p in YT_CACHE.glob("batch_*.json")]
    next_num = max(existing, default=0) + 1
    for i, ids in enumerate(batches):
        try:
            resp = get_json(YT_VIDEOS_URL,
                            params={"part": "snippet,statistics", "id": ",".join(ids),
                                    "maxResults": YT_BATCH_SIZE, "key": api_key},
                            label=f"YouTube batch {i + 1}/{len(batches)}")
        except QuotaExceeded:
            log.error("YouTube quota exceeded after %d of %d batches. Progress is cached; "
                      "rerun after the quota resets (midnight Pacific).", i, len(batches))
            raise
        write_atomic(YT_CACHE / f"batch_{next_num:04d}.json",
                     json.dumps({"requested_ids": ids, "response": resp}, indent=2))
        next_num += 1
        for item in resp.get("items", []):
            items[item["id"]] = item
    return items


def to_int(value):
    """YouTube sends counts as strings. A missing count means it's hidden or disabled."""
    return int(value) if value not in (None, "") else None


def video_info(item):
    stats, snippet = item.get("statistics", {}), item.get("snippet", {})
    return {
        "id": item["id"],
        "views": to_int(stats.get("viewCount")),
        "likes": to_int(stats.get("likeCount")),
        "comments": to_int(stats.get("commentCount")),
        "published_at": snippet.get("publishedAt"),
        "channel": snippet.get("channelTitle"),
        "title": snippet.get("title"),
    }


# --- Stage 3: pick trailers and build output --------------------------------

def build_row(imdb_id, movie, record, yt_items):
    # Unfilled columns stay None, which csv writes as an empty cell (not 0).
    row = dict.fromkeys(OUTPUT_COLUMNS)
    row.update(imdb_id=imdb_id, title=movie["originalTitle"])

    if record is None:
        row["status"] = "fetch_error"  # TMDB request failed; rerun to retry
        return row
    matches = (record.get("find") or {}).get("movie_results") or []
    if not matches:
        row["status"] = "no_tmdb_match"
        return row
    row["tmdb_title"] = matches[0].get("title")
    row["year"] = (matches[0].get("release_date") or "")[:4] or None

    candidate_ids, _ = trailer_candidates(record)
    row["num_candidates"] = len(candidate_ids)
    if not candidate_ids:
        row["status"] = "no_trailer"
        return row
    available = [video_info(yt_items[v]) for v in candidate_ids if v in yt_items]
    if not available:
        row["status"] = "video_unavailable"  # TMDB lists it, YouTube doesn't return it
        return row

    # ISO-8601 timestamps sort correctly as strings. A missing date sorts last.
    primary = min(available, key=lambda v: v["published_at"] or "9999")
    most_viewed = max(available, key=lambda v: v["views"] if v["views"] is not None else -1)
    row.update(
        primary_video_id=primary["id"], primary_views=primary["views"],
        primary_likes=primary["likes"], primary_comments=primary["comments"],
        primary_published_at=primary["published_at"], primary_channel=primary["channel"],
        primary_video_title=primary["title"],
        most_viewed_video_id=most_viewed["id"], most_viewed_views=most_viewed["views"],
        most_viewed_likes=most_viewed["likes"],
        status="likes_hidden" if primary["likes"] is None else "ok",
    )
    return row


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    load_dotenv(REPO_ROOT / ".env")
    tmdb_key, yt_key = os.getenv("TMDB_API_KEY"), os.getenv("YOUTUBE_API_KEY")
    missing = [name for name, val in [("TMDB_API_KEY", tmdb_key), ("YOUTUBE_API_KEY", yt_key)]
               if not val]
    if missing:
        log.error("Missing from %s: %s", REPO_ROOT / ".env", ", ".join(missing))
        return 1

    for d in (TMDB_CACHE, YT_CACHE, OUTPUT_CSV.parent):
        d.mkdir(parents=True, exist_ok=True)
    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        movies = list(csv.DictReader(f))

    # Stage 1: TMDB
    auth_params, auth_headers = tmdb_auth(tmdb_key)
    records = {}
    for n, movie in enumerate(movies, 1):
        imdb_id = movie["id"].strip()
        try:
            records[imdb_id] = fetch_tmdb(imdb_id, auth_params, auth_headers)
        except APIError as e:
            if e.status == 401:  # wrong key: no point trying the other movies
                log.error("TMDB rejected the API key (HTTP 401). Check TMDB_API_KEY.")
                return 1
            log.warning("%s (will retry on next run)", e)
            records[imdb_id] = None
        if n % 50 == 0 or n == len(movies):
            log.info("TMDB: %d/%d movies", n, len(movies))

    # Stage 2: YouTube
    all_ids = {vid for r in records.values() if r for vid in trailer_candidates(r)[0]}
    try:
        yt_items = fetch_youtube(all_ids, yt_key)
    except QuotaExceeded:
        return 2
    except APIError as e:
        log.error("%s. Stopping; rerun to resume from cache.", e)
        return 1

    # Stage 3: output (only written once every stage has completed)
    rows = [build_row(m["id"].strip(), m, records[m["id"].strip()], yt_items) for m in movies]
    with OUTPUT_CSV.with_name(OUTPUT_CSV.name + ".tmp").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(OUTPUT_CSV.with_name(OUTPUT_CSV.name + ".tmp"), OUTPUT_CSV)

    counts = Counter(r["status"] for r in rows)
    unofficial_only = sum(1 for r in records.values()
                          if r and not trailer_candidates(r)[0] and trailer_candidates(r)[1])
    log.info("Done. Wrote %s", OUTPUT_CSV.relative_to(REPO_ROOT))
    log.info("  movies processed:       %d", len(rows))
    log.info("  ok:                     %d", counts["ok"])
    log.info("  no trailer:             %d  (%d of these have only unofficial trailers)",
             counts["no_trailer"], unofficial_only)
    log.info("  likes hidden:           %d", counts["likes_hidden"])
    log.info("  no TMDB match:          %d", counts["no_tmdb_match"])
    log.info("  video unavailable:      %d", counts["video_unavailable"])
    if counts["fetch_error"]:
        log.warning("  fetch errors:           %d  (rerun to retry)", counts["fetch_error"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
