# Spotify API Results

This folder contains a helper script for fetching current Spotify Web API track metadata for the proj04 selected genres:

- `classical`
- `hip-hop`
- `country`
- `edm`
- `jazz`

By default, the script keeps `1000` rows per genre from `music_tracks.csv`, producing `5000` output rows.

## Important Limitations

The official Spotify Web API does **not** return raw track play counts or stream counts. Spotify's 2026 development-mode changes also removed batch track fetching, so the script uses `GET /tracks/{id}` one track at a time instead of `GET /tracks?ids=...`.

Spotify's development-mode field changes may also remove the formerly available track-level `popularity` value from responses. For that reason, the output CSV includes:

- `api_popularity`: current popularity returned by Spotify's official API, if available
- `play_count`: left blank
- `play_count_note`: explanation that play counts are not available from the official API

## Setup

Create a Spotify developer app, then set your credentials as environment variables:

```bash
export SPOTIFY_CLIENT_ID="your-client-id"
export SPOTIFY_CLIENT_SECRET="your-client-secret"
```

## Run

From `projects/proj04`:

```bash
python3 spotify_api_results/fetch_spotify_track_metadata.py
```

Expected outputs:

- `spotify_api_results/spotify_tracks_current_popularity.csv`
- `spotify_api_results/spotify_api_failures.csv`
- `spotify_api_results/run_summary.json`
- `spotify_api_results/spotify_track_cache.jsonl`

The script resumes from `spotify_track_cache.jsonl` by default, so interrupted runs do not lose completed API responses.

To fetch only 100 rows per genre for testing:

```bash
python3 spotify_api_results/fetch_spotify_track_metadata.py --per-genre 100 --expected-rows 500
```

If Spotify rate-limits the run, use a slower request pace:

```bash
python3 spotify_api_results/fetch_spotify_track_metadata.py --sleep 0.25 --progress-every 25
```

If Spotify returns a very long `Retry-After` value, the script exits instead of silently sleeping for hours. Wait until the limit resets, then rerun the same command; completed responses are reused from the cache.

## Output Columns

The main CSV preserves one row per selected row in the local dataset, including duplicate `track_id` rows if they exist in `music_tracks.csv`. Useful columns include:

- `track_genre`
- `dataset_track_id`
- `dataset_track_name`
- `dataset_artists`
- `dataset_popularity`
- `api_track_id`
- `api_track_name`
- `api_artist_names`
- `api_album_name`
- `api_release_date`
- `api_popularity`
- `popularity_changed`
- `api_spotify_url`
- `api_isrc`
- `play_count`
- `play_count_note`
