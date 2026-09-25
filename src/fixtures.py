import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import CSV_COLUMNS, TIMEZONE


def _safe_id(obj):
    return (obj or {}).get("id", "") if isinstance(obj, dict) else ""


def _safe_name(obj):
    return (obj or {}).get("name", "") if isinstance(obj, dict) else ""


def _venue_name(match: dict) -> str:
    venue = match.get("venue")
    if isinstance(venue, dict):
        return venue.get("name", "") or venue.get("displayName", "")
    if isinstance(venue, str):
        return venue
    return ""


def parse_match(match: dict, competition_name: str, competition_id: str, season: str) -> dict:
    kickoff_raw = match.get("kickoffAt")
    if not kickoff_raw:
        raise ValueError(f"Match {match.get('id')} has no kickoffAt")

    # OpenFoot documents kickoffAt as ISO-8601 UTC.
    dt_utc = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00"))
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_utc = dt_utc.astimezone(timezone.utc)
    dt_ist = dt_utc.astimezone(ZoneInfo(TIMEZONE))

    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    return {
        "fixture_id": str(match.get("id", "")),
        "competition": competition_name,
        "competition_id": competition_id,
        "season": season,
        "date_ist": dt_ist.strftime("%Y-%m-%d"),
        "time_ist": dt_ist.strftime("%H:%M"),
        "datetime_ist": dt_ist.isoformat(timespec="minutes"),
        "datetime_utc": dt_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "home_team": _safe_name(home),
        "home_team_id": _safe_id(home),
        "away_team": _safe_name(away),
        "away_team_id": _safe_id(away),
        "status": match.get("status", "unknown"),
        "venue": _venue_name(match),
        "last_updated": now_utc,
    }


def load_csv(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {
            row["fixture_id"]: row
            for row in reader
            if row.get("fixture_id")
        }


def save_csv(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    sorted_rows = sorted(
        rows.values(),
        key=lambda r: (
            r.get("datetime_ist", "9999-99-99T99:99"),
            r.get("competition", ""),
            r.get("home_team", ""),
        ),
    )

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)


def upsert_matches(
    existing: dict[str, dict],
    matches: list[dict],
    competition_name: str,
    competition_id: str,
    season: str,
) -> tuple[int, int]:
    added = 0
    updated = 0

    for match in matches:
        fixture_id = str(match.get("id", ""))
        if not fixture_id:
            continue

        row = parse_match(match, competition_name, competition_id, season)

        if fixture_id in existing:
            if existing[fixture_id] != row:
                updated += 1
            existing[fixture_id] = row
        else:
            added += 1
            existing[fixture_id] = row

    return added, updated
