import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .config import (
    COMPETITIONS,
    FUTURE_AUDIT_DAYS,
    FUTURE_AUDIT_HOUR_IST,
    SEASON,
    TIMEZONE,
)
from .fixtures import (
    build_fixture_rows,
    upsert_master_fixtures,
    write_instagram_csv,
)
from .openfoot_api import OpenFootAPIError, OpenFootClient


IST = ZoneInfo(TIMEZONE)


def should_run_future_audit() -> bool:
    """
    Run the expensive date-level freshness audit only once per day.

    GitHub Actions executes the workflow four times per day.
    The 05:30 IST run performs the additional upcoming-date checks.
    """
    now_ist = datetime.now(IST)

    return now_ist.hour == FUTURE_AUDIT_HOUR_IST


def get_future_audit_days() -> int:
    """
    Allow manual GitHub Actions runs to override the normal horizon.

    Example:
        FUTURE_AUDIT_DAYS=30

    Scheduled runs use the configured default.
    """
    raw_value = os.getenv("FUTURE_AUDIT_DAYS", "").strip()

    if not raw_value:
        return FUTURE_AUDIT_DAYS

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"FUTURE_AUDIT_DAYS must be an integer, got {raw_value!r}"
        ) from exc

    if value < 1:
        raise RuntimeError(
            "FUTURE_AUDIT_DAYS must be greater than zero."
        )

    return value


def fetch_fresh_upcoming_matches(
    client: OpenFootClient,
    competition_name: str,
    competition_id: str,
    season: str,
    days: int,
) -> list[dict]:
    """
    Fetch upcoming dates individually.

    This acts as a freshness overlay over the season-level response.
    Newly added/rescheduled fixtures are therefore discovered even if
    the season-level response is stale.
    """
    today = datetime.now(IST).date()

    fresh_matches: dict[str, dict] = {}

    print(
        f" Freshness audit: next {days} days "
        f"for {competition_name}"
    )

    for offset in range(days):
        match_date = today + timedelta(days=offset)

        try:
            matches = client.get_matches_for_date(
                competition_id=competition_id,
                season=season,
                match_date=match_date,
            )
        except OpenFootAPIError as exc:
            raise RuntimeError(
                f"Freshness audit failed for "
                f"{competition_name} on {match_date}: {exc}"
            ) from exc

        for match in matches:
            fixture_id = str(match.get("id") or "").strip()

            if fixture_id:
                fresh_matches[fixture_id] = match

    print(
        f" Freshness audit discovered "
        f"{len(fresh_matches)} fixtures"
    )

    return list(fresh_matches.values())


def main() -> None:
    load_dotenv()

    api_key = os.getenv("OPENFOOT_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENFOOT_API_KEY environment variable is missing."
        )

    client = OpenFootClient(api_key)

    all_rows = []

    run_future_audit = should_run_future_audit()

    audit_days = get_future_audit_days()

    print("=" * 70)
    print("OPENFOOT FOOTBALL FIXTURE SYNC")
    print(f"Season: {SEASON}")
    print(f"Competitions: {len(COMPETITIONS)}")
    print(f"Future freshness audit: {run_future_audit}")

    if run_future_audit:
        print(f"Future audit horizon: {audit_days} days")

    print("=" * 70)

    for competition_name, competition_id in COMPETITIONS.items():

        print(
            f"\nFetching: {competition_name} "
            f"({competition_id})"
        )

        try:
            # -------------------------------------------------
            # 1. Full season fetch
            # -------------------------------------------------

            matches = client.get_matches(
                competition_id=competition_id,
                season=SEASON,
            )

            print(
                f" OpenFoot returned {len(matches)} "
                "season-level matches"
            )

            # -------------------------------------------------
            # 2. Upcoming freshness overlay
            # -------------------------------------------------

            if run_future_audit:
                fresh_matches = fetch_fresh_upcoming_matches(
                    client=client,
                    competition_name=competition_name,
                    competition_id=competition_id,
                    season=SEASON,
                    days=audit_days,
                )

                # Merge by stable fixture ID.
                #
                # Date-level data wins because it is intentionally
                # being used as the freshness layer.
                merged_matches = {
                    str(match.get("id")): match
                    for match in matches
                    if match.get("id")
                }

                for match in fresh_matches:
                    fixture_id = str(match.get("id") or "").strip()

                    if fixture_id:
                        merged_matches[fixture_id] = match

                matches = list(merged_matches.values())

                print(
                    f" After freshness overlay: "
                    f"{len(matches)} unique matches"
                )

            # -------------------------------------------------
            # 3. Normalize
            # -------------------------------------------------

            rows = build_fixture_rows(
                matches=matches,
                competition_name=competition_name,
                competition_id=competition_id,
                season=SEASON,
            )

            print(
                f" Normalised {len(rows)} matches"
            )

            if not rows:
                raise RuntimeError(
                    f"{competition_name} produced zero usable "
                    "fixtures. CSV files were not updated."
                )

            all_rows.extend(rows)

        except OpenFootAPIError as exc:
            raise RuntimeError(
                f"Failed to fetch {competition_name}: {exc}"
            ) from exc

    if not all_rows:
        raise RuntimeError(
            "OpenFoot returned zero usable fixtures across "
            "all competitions. CSV files were not updated."
        )

    # ---------------------------------------------------------
    # 4. Global duplicate protection
    # ---------------------------------------------------------

    unique_rows = {}

    for row in all_rows:
        fixture_id = str(row.get("fixture_id") or "").strip()

        if not fixture_id:
            raise RuntimeError(
                "A normalized fixture is missing fixture_id."
            )

        unique_rows[fixture_id] = row

    all_rows = list(unique_rows.values())

    print("\n" + "=" * 70)
    print(f"Total unique fixtures fetched: {len(all_rows)}")
    print("=" * 70)

    # ---------------------------------------------------------
    # 5. Only now modify CSV files
    # ---------------------------------------------------------

    master_rows = upsert_master_fixtures(
        new_rows=all_rows,
    )

    print(
        f"\nMaster CSV updated with "
        f"{len(master_rows)} total fixtures."
    )

    # ---------------------------------------------------------
    # 6. Generate Instagram CSV
    # ---------------------------------------------------------

    write_instagram_csv(
        master_rows=master_rows,
    )

    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
