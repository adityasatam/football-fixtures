import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import (
    CSV_COLUMNS,
    DATA_DIR,
    DATA_FILE,
    INSTAGRAM_COLUMNS,
    INSTAGRAM_DATA_FILE,
    TIMEZONE,
    COMPETITION_SHORT_NAMES,
)


IST = ZoneInfo(TIMEZONE)


def _get_team(match: dict, side: str) -> tuple[str, str]:
    """
    Extract team ID and team name from OpenFoot's response.
    """
    team = match.get(side) or {}

    if not isinstance(team, dict):
        return "", str(team)

    return (
        str(team.get("id") or ""),
        str(team.get("name") or ""),
    )


def _get_venue(match: dict) -> str:
    """
    OpenFoot may return venue as a string or object.
    """
    venue = match.get("venue")

    if not venue:
        return ""

    if isinstance(venue, str):
        return venue

    if isinstance(venue, dict):
        return str(
            venue.get("name")
            or venue.get("venueName")
            or venue.get("stadium")
            or ""
        )

    return str(venue)


def _parse_kickoff(kickoff_at: str) -> tuple[datetime, datetime]:
    """
    Convert OpenFoot UTC kickoffAt into:
      - UTC datetime
      - IST datetime
    """
    if not kickoff_at:
        raise ValueError("Missing kickoffAt")

    normalized = kickoff_at.replace("Z", "+00:00")

    dt = datetime.fromisoformat(normalized)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    dt_utc = dt.astimezone(timezone.utc)
    dt_ist = dt_utc.astimezone(IST)

    return dt_utc, dt_ist


def _normalise_status(status: str) -> str:
    status = str(status or "unknown").strip().lower()

    valid_statuses = {
        "scheduled",
        "live",
        "finished",
        "postponed",
        "cancelled",
        "unknown",
    }

    return status if status in valid_statuses else "unknown"


def _safe_hashtag(value: str) -> str:
    """
    Convert a team/competition name into a simple Instagram hashtag.

    Example:
        Manchester City -> #ManchesterCity
        Premier League -> #PremierLeague
    """
    value = value.replace("&", "and")

    words = re.findall(r"[A-Za-z0-9]+", value)

    if not words:
        return ""

    return "#" + "".join(words)


def _instagram_caption(
    competition: str,
    home_team: str,
    away_team: str,
    match_date: str,
    match_day: str,
    kickoff_ist: str,
    status: str,
) -> str:
    """
    Generate an Instagram-ready caption.
    """
    try:
        formatted_date = datetime.strptime(
            match_date,
            "%Y-%m-%d",
        ).strftime("%d %b %Y")
    except ValueError:
        formatted_date = match_date

    hashtags = [
        _safe_hashtag(competition),
        _safe_hashtag(home_team),
        _safe_hashtag(away_team),
        "#Football",
    ]

    hashtags = [tag for tag in hashtags if tag]

    return (
        f"{home_team} vs {away_team}\n\n"
        f"📅 {match_day}, {formatted_date}\n"
        f"⏰ {kickoff_ist} IST\n\n"
        f"{' '.join(hashtags)}"
    )


def parse_match(
    match: dict,
    competition_name: str,
    competition_id: str,
    season: str,
) -> dict:
    """
    Convert one OpenFoot match into our master CSV format.
    """
    fixture_id = str(match.get("id") or "").strip()

    if not fixture_id:
        raise ValueError("Match is missing fixture ID")

    kickoff_at = match.get("kickoffAt")

    dt_utc, dt_ist = _parse_kickoff(kickoff_at)

    home_team_id, home_team = _get_team(match, "homeTeam")
    away_team_id, away_team = _get_team(match, "awayTeam")

    if not home_team or not away_team:
        raise ValueError(
            f"Fixture {fixture_id} is missing home/away team information"
        )

    status = _normalise_status(match.get("status"))

    return {
        "fixture_id": fixture_id,
        "competition": competition_name,
        "competition_id": competition_id,
        "competition_short": COMPETITION_SHORT_NAMES.get(
            competition_name,
            competition_name,
        ),
        "season": season,
        "date_ist": dt_ist.strftime("%Y-%m-%d"),
        "time_ist": dt_ist.strftime("%I:%M %p"),
        "datetime_ist": dt_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "datetime_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "match_day": dt_ist.strftime("%A"),
        "home_team": home_team,
        "home_team_id": home_team_id,
        "away_team": away_team,
        "away_team_id": away_team_id,
        "status": status,
        "venue": _get_venue(match),
        "last_updated": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }


def build_fixture_rows(
    matches: list[dict],
    competition_name: str,
    competition_id: str,
    season: str,
) -> list[dict]:
    """
    Convert all matches for one competition.
    """
    rows = []

    for match in matches:
        try:
            row = parse_match(
                match=match,
                competition_name=competition_name,
                competition_id=competition_id,
                season=season,
            )

            rows.append(row)

        except ValueError as exc:
            print(
                f"WARNING: Skipping malformed match in "
                f"{competition_name}: {exc}"
            )

    return rows


def _read_existing_csv(path: Path) -> dict[str, dict]:
    """
    Read an existing CSV into a dictionary keyed by fixture_id.
    """
    if not path.exists():
        return {}

    existing = {}

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            fixture_id = str(
                row.get("fixture_id") or ""
            ).strip()

            if fixture_id:
                existing[fixture_id] = row

    return existing


def _write_csv(
    path: Path,
    rows: list[dict],
    columns: list[str],
) -> None:
    """
    Write CSV atomically to avoid leaving a partially-written file.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_suffix(".tmp")

    with temp_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    column: row.get(column, "")
                    for column in columns
                }
            )

    temp_path.replace(path)


def upsert_master_fixtures(
    new_rows: list[dict],
) -> list[dict]:
    """
    Upsert fixtures using fixture_id as the stable key.

    Existing fixtures are preserved.
    Newly fetched fixtures replace existing records with the same ID.
    """
    existing = _read_existing_csv(DATA_FILE)

    for row in new_rows:
        existing[row["fixture_id"]] = row

    rows = list(existing.values())

    rows.sort(
        key=lambda row: (
            row.get("datetime_ist", ""),
            row.get("competition", ""),
            row.get("home_team", ""),
        )
    )

    _write_csv(
        path=DATA_FILE,
        rows=rows,
        columns=CSV_COLUMNS,
    )

    return rows


def _build_instagram_rows(
    master_rows: list[dict],
) -> list[dict]:
    """
    Create Instagram-friendly records from the master fixture data.

    STATUS RULE
    -----------
    OpenFoot can occasionally continue returning "scheduled"
    for a fixture whose kickoff time has already passed.

    Therefore:

        scheduled + kickoff in the future
            -> scheduled

        scheduled + kickoff already passed
            -> finished

    Source statuses such as live, finished, postponed and
    cancelled are preserved.

    This prevents stale "scheduled" records from appearing
    with negative days_until_match values such as -1, -2, -3.
    """

    # Use the exact current IST datetime for status correction.
    now_ist = datetime.now(IST)

    # Keep calendar date separately for days_until_match,
    # is_today and is_tomorrow.
    today = now_ist.date()

    instagram_rows = []

    for row in master_rows:

        # ----------------------------------------------------
        # Parse match date
        # ----------------------------------------------------

        try:
            match_date = datetime.strptime(
                row["date_ist"],
                "%Y-%m-%d",
            ).date()

        except (ValueError, TypeError, KeyError):
            match_date = None

        # ----------------------------------------------------
        # Calculate calendar days until match.
        #
        # IMPORTANT:
        # Negative values are still allowed here.
        #
        # Example:
        #   Today = 03 Oct
        #   Match = 01 Oct
        #   days_until_match = -2
        #
        # The important correction is that a negative-day
        # fixture must NOT remain "scheduled" if its kickoff
        # time has already passed.
        # ----------------------------------------------------

        if match_date is not None:
            days_until = (
                match_date - today
            ).days

        else:
            days_until = ""

        # ----------------------------------------------------
        # Original source status
        # ----------------------------------------------------

        source_status = str(
            row.get(
                "status",
                "unknown",
            )
        ).strip().lower()

        # ----------------------------------------------------
        # Parse exact kickoff datetime.
        #
        # datetime_ist is generated from the original UTC
        # kickoff timestamp and represents IST.
        # ----------------------------------------------------

        kickoff_ist = None

        datetime_ist_value = str(
            row.get(
                "datetime_ist",
                "",
            )
        ).strip()

        if datetime_ist_value:
            try:
                kickoff_ist = datetime.strptime(
                    datetime_ist_value,
                    "%Y-%m-%d %H:%M:%S",
                ).replace(
                    tzinfo=IST
                )

            except ValueError:
                kickoff_ist = None

        # ----------------------------------------------------
        # Correct stale "scheduled" status.
        #
        # ONLY scheduled is overridden.
        #
        # We preserve:
        #   live
        #   finished
        #   postponed
        #   cancelled
        #   unknown
        #
        # This means we do not accidentally change an
        # explicitly postponed/cancelled fixture.
        # ----------------------------------------------------

        effective_status = source_status

        if (
            source_status == "scheduled"
            and kickoff_ist is not None
            and kickoff_ist <= now_ist
        ):
            effective_status = "finished"

        # ----------------------------------------------------
        # Determine Instagram post type from EFFECTIVE status.
        # ----------------------------------------------------

        if effective_status in {
            "scheduled",
            "postponed",
        }:
            post_type = "MATCH_PREVIEW"

        elif effective_status == "live":
            post_type = "LIVE_MATCH"

        elif effective_status == "finished":
            post_type = "MATCH_RESULT"

        elif effective_status == "cancelled":
            post_type = "MATCH_CANCELLED"

        else:
            post_type = "FOOTBALL_UPDATE"

        # ----------------------------------------------------
        # Today / tomorrow flags.
        # ----------------------------------------------------

        is_today = (
            match_date == today
            if match_date is not None
            else False
        )

        tomorrow = today.fromordinal(
            today.toordinal() + 1
        )

        is_tomorrow = (
            match_date == tomorrow
            if match_date is not None
            else False
        )

        # ----------------------------------------------------
        # Instagram caption.
        #
        # Use effective_status rather than stale source status.
        # ----------------------------------------------------

        caption = _instagram_caption(
            competition=row["competition"],
            home_team=row["home_team"],
            away_team=row["away_team"],
            match_date=row["date_ist"],
            match_day=row["match_day"],
            kickoff_ist=row["time_ist"],
            status=effective_status,
        )

        # ----------------------------------------------------
        # Build Instagram row.
        # ----------------------------------------------------

        instagram_rows.append(
            {
                "fixture_id": row["fixture_id"],
                "competition": row["competition"],
                "competition_short": row["competition_short"],
                "season": row["season"],
                "match_date": row["date_ist"],
                "match_day": row["match_day"],
                "kickoff_ist": row["time_ist"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],

                # IMPORTANT:
                # Write effective_status, NOT source_status.
                "status": effective_status,

                "venue": row["venue"],
                "is_today": str(is_today).lower(),
                "is_tomorrow": str(is_tomorrow).lower(),
                "days_until_match": days_until,
                "post_type": post_type,
                "instagram_title": (
                    f"{row['home_team']} vs "
                    f"{row['away_team']}"
                ),
                "instagram_caption": caption,
            }
        )

    # --------------------------------------------------------
    # Sort chronologically.
    # --------------------------------------------------------

    instagram_rows.sort(
        key=lambda row: (
            row.get("match_date", ""),
            row.get("kickoff_ist", ""),
            row.get("competition", ""),
        )
    )

    return instagram_rows


def write_instagram_csv(
    master_rows: list[dict],
) -> None:
    """
    Generate the Instagram-friendly CSV.
    """
    instagram_rows = _build_instagram_rows(master_rows)

    _write_csv(
        path=INSTAGRAM_DATA_FILE,
        rows=instagram_rows,
        columns=INSTAGRAM_COLUMNS,
    )

    print(
        f"Instagram CSV written: "
        f"{INSTAGRAM_DATA_FILE} "
        f"({len(instagram_rows)} rows)"
    )
