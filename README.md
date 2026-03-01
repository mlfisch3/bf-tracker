# BladeForums Thread View Tracker (Tracker Service)

This repository contains the always-on tracker service for monitoring view counts on BladeForums threads. It runs on a schedule via GitHub Actions and writes time-series data to the `data/` directory.

## What this does

- Fetches BladeForums subforum pages at a polite rate.
- Locates target threads by exact title match within their subforum.
- Records view counts with timestamps.
- Commits updated data back to this repository.

## Repository layout

- `tracker/`: core tracking logic.
- `data/`: configuration and collected time-series data.
- `.github/workflows/track.yml`: scheduled job.

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m tracker.runner
```

## Configuration

Edit `data/config.json` and `data/threads.json` to control tracking targets and rate limits.

## GitHub Actions

The workflow runs every 30 minutes by default (UTC). It can also be triggered manually.

## Notes

- This is intended to run without logging into BladeForums.
- The scraper uses polite rate limiting, jittered delays, and backoff.
