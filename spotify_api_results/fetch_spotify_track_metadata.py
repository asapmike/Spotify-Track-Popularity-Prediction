#!/usr/bin/env python3
"""
Fetch current Spotify Web API metadata for the selected proj04 tracks.

The official Spotify Web API does not expose raw track play counts/stream
counts. Spotify's development-mode API changes also removed the batch track
fetch endpoint and may omit the formerly available track `popularity` field.
This script fetches tracks one-by-one and keeps missing unavailable fields
explicitly blank instead of inventing values.

Credentials:
    export SPOTIFY_CLIENT_ID="..."
    export SPOTIFY_CLIENT_SECRET="..."

Example:
    python3 spotify_api_results/fetch_spotify_track_metadata.py
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GENRES = ["classical", "hip-hop", "country", "edm", "jazz"]
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_TRACK_URL = "https://api.spotify.com/v1/tracks/{track_id}"


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Fetch current Spotify API popularity for selected proj04 tracks."
    )
    parser.add_argument(
        "--tracks-csv",
        type=Path,
        default=project_dir / "Spotify Music Tracks" / "Data" / "music_tracks.csv",
        help="Path to the local music_tracks.csv file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory where output CSV/JSON files will be written.",
    )
    parser.add_argument(
        "--genres",
        nargs="+",
        default=DEFAULT_GENRES,
        help="Genres to include.",
    )
    parser.add_argument(
        "--per-genre",
        type=int,
        default=1000,
        help="Number of rows to keep from each genre. Use 1000 for 5000 rows across 5 genres.",
    )
    parser.add_argument(
        "--market",
        default="US",
        help="Spotify market code to pass to the API.",
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        default=5000,
        help="Warn if the output does not contain this many rows.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.05,
        help="Seconds to sleep between track requests.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retries for rate limits and transient server errors.",
    )
    parser.add_argument(
        "--max-rate-limit-sleep",
        type=float,
        default=300,
        help="Do not sleep longer than this many seconds for a Spotify 429 Retry-After.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Print progress after this many unique track requests.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume from cached API responses in out-dir/spotify_track_cache.jsonl.",
    )
    return parser.parse_args()


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    max_retries: int = 5,
    max_rate_limit_sleep: float = 300,
) -> dict[str, Any]:
    headers = headers or {}

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(
            url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After")
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < max_retries:
                sleep_for = float(retry_after or 2 ** attempt)
                if sleep_for > max_rate_limit_sleep:
                    raise RuntimeError(
                        f"HTTP 429 for {url}: Spotify requested Retry-After={sleep_for:.0f}s, "
                        f"which exceeds --max-rate-limit-sleep={max_rate_limit_sleep:.0f}s. {body}"
                    ) from exc
                print(
                    f"Rate limited by Spotify; sleeping {sleep_for:.0f}s before retry "
                    f"({attempt + 1}/{max_retries})",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(sleep_for)
                continue
            if 500 <= exc.code < 600 and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Request failed for {url}: {exc}") from exc

    raise RuntimeError(f"Request failed after {max_retries} retries: {url}")


def get_access_token(client_id: str, client_secret: str, max_retries: int) -> str:
    auth = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = urllib.parse.urlencode(
        {"grant_type": "client_credentials"}).encode("utf-8")
    payload = request_json(
        SPOTIFY_TOKEN_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
        max_retries=max_retries,
    )
    return payload["access_token"]


def read_selected_tracks(
    tracks_csv: Path, genres: list[str], per_genre: int
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    counts = {genre: 0 for genre in genres}
    genre_set = set(genres)

    with tracks_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            genre = row["track_genre"]
            if genre in genre_set and counts[genre] < per_genre:
                selected.append(row)
                counts[genre] += 1

    missing = {genre: per_genre - count for genre,
               count in counts.items() if count < per_genre}
    if missing:
        raise ValueError(
            f"Not enough rows for requested per-genre sample: {missing}")

    return selected


def fetch_tracks(
    track_ids: list[str],
    *,
    token: str,
    market: str,
    sleep: float,
    max_retries: int,
    progress_every: int,
    cache_path: Path,
    resume: bool,
    max_rate_limit_sleep: float,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    headers = {"Authorization": f"Bearer {token}"}
    unique_ids = list(dict.fromkeys(track_ids))
    fetched: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    if resume and cache_path.exists():
        with cache_path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                cached = json.loads(line)
                if cached.get("ok"):
                    track = cached["track"]
                    fetched[cached["requested_track_id"]] = track
                    if track.get("id"):
                        fetched[track["id"]] = track
                else:
                    failures.append(
                        {
                            "track_id": cached["requested_track_id"],
                            "request_index": cached.get("request_index", ""),
                            "error": cached.get("error", ""),
                        }
                    )

    already_done = set(fetched) | {failure["track_id"] for failure in failures}

    total = len(unique_ids)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("a", encoding="utf-8") as cache_file:
        for index, track_id in enumerate(unique_ids, start=1):
            if track_id in already_done:
                if progress_every > 0 and (index == 1 or index % progress_every == 0 or index == total):
                    print(
                        f"Progress: {index}/{total} unique track IDs considered; "
                        f"{len(fetched)} fetched, {len(failures)} failed, "
                        f"{len(already_done)} cached",
                        file=sys.stderr,
                        flush=True,
                    )
                continue

            query = urllib.parse.urlencode({"market": market})
            url = f"{SPOTIFY_TRACK_URL.format(track_id=urllib.parse.quote(track_id))}?{query}"
            try:
                track = request_json(
                    url,
                    headers=headers,
                    max_retries=max_retries,
                    max_rate_limit_sleep=max_rate_limit_sleep,
                )
            except RuntimeError as exc:
                failure = {
                    "track_id": track_id,
                    "request_index": str(index),
                    "error": str(exc),
                }
                failures.append(failure)
                cache_file.write(
                    json.dumps(
                        {
                            "requested_track_id": track_id,
                            "request_index": str(index),
                            "ok": False,
                            "error": str(exc),
                            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    + "\n"
                )
                cache_file.flush()
                already_done.add(track_id)
                continue

            fetched[track["id"]] = track
            if track["id"] != track_id:
                fetched[track_id] = track

            cache_file.write(
                json.dumps(
                    {
                        "requested_track_id": track_id,
                        "request_index": str(index),
                        "ok": True,
                        "track": track,
                        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
                + "\n"
            )
            cache_file.flush()
            already_done.add(track_id)

            time.sleep(sleep)

            if progress_every > 0 and (index == 1 or index % progress_every == 0 or index == total):
                print(
                    f"Progress: {index}/{total} unique track IDs requested; "
                    f"{len(fetched)} fetched, {len(failures)} failed",
                    file=sys.stderr,
                    flush=True,
                )

    return fetched, failures


def output_row(local_row: dict[str, str], api_track: dict[str, Any] | None) -> dict[str, Any]:
    album = (api_track or {}).get("album") or {}
    artists = (api_track or {}).get("artists") or []
    external_urls = (api_track or {}).get("external_urls") or {}
    external_ids = (api_track or {}).get("external_ids") or {}

    api_artist_names = ";".join(artist.get("name", "") for artist in artists)
    api_artist_ids = ";".join(artist.get("id", "") for artist in artists)

    api_popularity = (api_track or {}).get("popularity")
    dataset_popularity = int(
        local_row["popularity"]) if local_row["popularity"] else None

    return {
        "track_genre": local_row["track_genre"],
        "dataset_track_id": local_row["track_id"],
        "dataset_track_name": local_row["track_name"],
        "dataset_artists": local_row["artists"],
        "dataset_album_name": local_row["album_name"],
        "dataset_popularity": dataset_popularity,
        "api_track_id": (api_track or {}).get("id"),
        "api_track_name": (api_track or {}).get("name"),
        "api_artist_names": api_artist_names,
        "api_artist_ids": api_artist_ids,
        "api_album_id": album.get("id"),
        "api_album_name": album.get("name"),
        "api_release_date": album.get("release_date"),
        "api_popularity": api_popularity,
        "popularity_changed": (
            None if api_popularity is None or dataset_popularity is None else api_popularity != dataset_popularity
        ),
        "api_duration_ms": (api_track or {}).get("duration_ms"),
        "api_explicit": (api_track or {}).get("explicit"),
        "api_is_playable": (api_track or {}).get("is_playable"),
        "api_spotify_url": external_urls.get("spotify"),
        "api_isrc": external_ids.get("isrc"),
        "play_count": None,
        "play_count_note": "Not available from the official Spotify Web API",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.",
            file=sys.stderr,
        )
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    selected_rows = read_selected_tracks(
        args.tracks_csv, args.genres, args.per_genre)
    track_ids = [row["track_id"] for row in selected_rows]
    try:
        token = get_access_token(client_id, client_secret, args.max_retries)
    except RuntimeError as exc:
        print(
            "Could not get a Spotify access token. Check that SPOTIFY_CLIENT_ID "
            "and SPOTIFY_CLIENT_SECRET match the current app settings.",
            file=sys.stderr,
        )
        print(str(exc), file=sys.stderr)
        return 3
    api_tracks, failures = fetch_tracks(
        track_ids,
        token=token,
        market=args.market,
        sleep=args.sleep,
        max_retries=args.max_retries,
        progress_every=args.progress_every,
        cache_path=args.out_dir / "spotify_track_cache.jsonl",
        resume=args.resume,
        max_rate_limit_sleep=args.max_rate_limit_sleep,
    )

    output_rows = [output_row(row, api_tracks.get(row["track_id"]))
                   for row in selected_rows]

    csv_path = args.out_dir / "spotify_tracks_current_popularity.csv"
    failures_path = args.out_dir / "spotify_api_failures.csv"
    summary_path = args.out_dir / "run_summary.json"

    write_csv(csv_path, output_rows)
    write_csv(failures_path, failures)

    summary = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "tracks_csv": str(args.tracks_csv),
        "genres": args.genres,
        "per_genre": args.per_genre,
        "expected_rows": args.expected_rows,
        "output_rows": len(output_rows),
        "unique_track_ids_requested": len(set(track_ids)),
        "unique_track_ids_fetched": len(api_tracks),
        "failed_unique_track_ids": len(failures),
        "market": args.market,
        "output_csv": str(csv_path),
        "failures_csv": str(failures_path),
        "cache_jsonl": str(args.out_dir / "spotify_track_cache.jsonl"),
        "play_count_available_from_official_api": False,
        "track_popularity_available_from_current_api_response": any(
            track.get("popularity") is not None for track in api_tracks.values()
        ),
        "warning": (
            "Official Spotify Web API does not expose raw play counts. "
            "In current development-mode responses, track popularity may also be omitted. "
            "Unavailable fields are intentionally blank."
        ),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if len(output_rows) != args.expected_rows:
        print(
            f"Warning: wrote {len(output_rows)} rows, expected {args.expected_rows}.",
            file=sys.stderr,
        )

    print(f"Wrote {len(output_rows)} rows to {csv_path}")
    print(f"Wrote summary to {summary_path}")
    if failures:
        print(
            f"Wrote {len(failures)} failures to {failures_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
