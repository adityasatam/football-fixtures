import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from .config import (
    COMPETITIONS,
    FUTURE_AUDIT_DAYS,
    FUTURE_AUDIT_HOUR_UTC,
    SEASON,
    TIMEZONE,
)
from .fixtures import (
    build_fixture_rows,
    upsert_master_fixtures,
    write_instagram_csv,
)
from .openfoot_api import (
    OpenFootAPIError,
    OpenFootClient,
)


UTC = timezone.utc

IST = ZoneInfo(TIMEZONE)


# =========================================================
# Future audit configuration
# =========================================================

def get_future_audit_days() -> int:
    """
    Read FUTURE_AUDIT_DAYS from the environment.

    Scheduled workflow:
        uses the configured default.

    Manual workflow:
        can override this value, e.g. 30.
    """

    raw_value = os.getenv(
        "FUTURE_AUDIT_DAYS",
        "",
    ).strip()

    if not raw_value:
        return FUTURE_AUDIT_DAYS

    try:
        value = int(raw_value)

    except ValueError as exc:
        raise RuntimeError(
            "FUTURE_AUDIT_DAYS must be an integer. "
            f"Received: {raw_value!r}"
        ) from exc

    if value < 1:
        raise RuntimeError(
            "FUTURE_AUDIT_DAYS must be greater than zero."
        )

    return value


def should_run_future_audit() -> bool:
    """
    Determine whether the future freshness audit should run.

    FORCE_FUTURE_AUDIT=true always enables it.

    Otherwise the scheduled 00:00 UTC execution performs it.
    """

    force_audit = (
        os.getenv(
            "FORCE_FUTURE_AUDIT",
            "",
        )
        .strip()
        .lower()
    )

    if force_audit in {
        "1",
        "true",
        "yes",
        "y",
    }:
        return True

    now_utc = datetime.now(UTC)

    return (
        now_utc.hour
        == FUTURE_AUDIT_HOUR_UTC
    )


# =========================================================
# Exact-date freshness audit
# =========================================================

def fetch_fresh_upcoming_matches(
    client: OpenFootClient,
    competition_name: str,
    competition_id: str,
    season: str,
    days: int,
) -> list[dict]:
    """
    Fetch upcoming fixture dates directly from OpenFoot.

    IMPORTANT:
    OpenFoot's date filter is based on the UTC calendar date.

    Therefore this function deliberately uses UTC rather than IST.

    This avoids missing fixtures around midnight when an IST date
    differs from the UTC date.
    """

    today_utc = datetime.now(UTC).date()

    fresh_matches: dict[str, dict] = {}

    print()
    print(
        f"Freshness audit: "
        f"{competition_name}"
    )

    print(
        f"UTC range: "
        f"{today_utc} -> "
        f"{today_utc + timedelta(days=days - 1)}"
    )

    for offset in range(days):

        match_date = (
            today_utc
            + timedelta(days=offset)
        )

        try:

            matches = client.get_matches_for_date(
                competition_id=competition_id,
                season=season,
                match_date=match_date,
            )

        except OpenFootAPIError as exc:

            raise RuntimeError(
                f"Freshness audit failed for "
                f"{competition_name} "
                f"on UTC date {match_date}: "
                f"{exc}"
            ) from exc

        if matches:

            print(
                f"  {match_date}: "
                f"{len(matches)} fixture(s)"
            )

        for match in matches:

            fixture_id = str(
                match.get("id") or ""
            ).strip()

            if not fixture_id:
                print(
                    "WARNING: date query returned "
                    "a fixture without an ID. "
                    "Skipping it."
                )
                continue

            fresh_matches[
                fixture_id
            ] = match

    print(
        f"Freshness audit discovered "
        f"{len(fresh_matches)} unique fixture(s) "
        f"for {competition_name}."
    )

    return list(
        fresh_matches.values()
    )


# =========================================================
# Merge fixtures
# =========================================================

def merge_matches(
    season_matches: list[dict],
    fresh_matches: list[dict],
) -> list[dict]:
    """
    Merge season-level and date-level results.

    Fixture ID is the stable key.

    Date-level data wins when the same fixture exists
    in both responses because the date-level request is
    specifically being used as the freshness layer.
    """

    merged: dict[str, dict] = {}

    for match in season_matches:

        fixture_id = str(
            match.get("id") or ""
        ).strip()

        if not fixture_id:
            continue

        merged[
            fixture_id
        ] = match

    for match in fresh_matches:

        fixture_id = str(
            match.get("id") or ""
        ).strip()

        if not fixture_id:
            continue

        merged[
            fixture_id
        ] = match

    return list(
        merged.values()
    )


# =========================================================
# Main
# =========================================================

def main() -> None:

    load_dotenv()

    api_key = os.getenv(
        "OPENFOOT_API_KEY",
        "",
    ).strip()

    if not api_key:

        raise RuntimeError(
            "OPENFOOT_API_KEY environment variable "
            "is missing."
        )

    client = OpenFootClient(
        api_key
    )

    all_rows = []

    run_future_audit = (
        should_run_future_audit()
    )

    audit_days = (
        get_future_audit_days()
    )

    now_utc = datetime.now(UTC)

    now_ist = now_utc.astimezone(IST)

    # -----------------------------------------------------
    # Run information
    # -----------------------------------------------------

    print()
    print("=" * 70)
    print("OPENFOOT FOOTBALL FIXTURE SYNC")
    print("=" * 70)

    print(
        f"UTC time : "
        f"{now_utc.isoformat()}"
    )

    print(
        f"IST time : "
        f"{now_ist.isoformat()}"
    )

    print(
        f"Season   : {SEASON}"
    )

    print(
        f"Competitions: "
        f"{len(COMPETITIONS)}"
    )

    print(
        f"Future freshness audit: "
        f"{run_future_audit}"
    )

    print(
        f"Future audit days: "
        f"{audit_days}"
    )

    print("=" * 70)

    # -----------------------------------------------------
    # Competition loop
    # -----------------------------------------------------

    for (
        competition_name,
        competition_id,
    ) in COMPETITIONS.items():

        print()
        print("-" * 70)

        print(
            f"Fetching: "
            f"{competition_name}"
        )

        print(
            f"Competition ID: "
            f"{competition_id}"
        )

        print("-" * 70)

        try:

            # =================================================
            # 1. Season-level request
            # =================================================

            season_matches = (
                client.get_matches(
                    competition_id=competition_id,
                    season=SEASON,
                )
            )

            print(
                f"Season-level response: "
                f"{len(season_matches)} fixture(s)"
            )

            matches = season_matches

            # =================================================
            # 2. Future date-level audit
            # =================================================

            if run_future_audit:

                fresh_matches = (
                    fetch_fresh_upcoming_matches(
                        client=client,
                        competition_name=competition_name,
                        competition_id=competition_id,
                        season=SEASON,
                        days=audit_days,
                    )
                )

                matches = merge_matches(
                    season_matches=season_matches,
                    fresh_matches=fresh_matches,
                )

                print(
                    f"Merged response: "
                    f"{len(matches)} unique fixture(s)"
                )

            # =================================================
            # 3. Normalize
            # =================================================

            rows = build_fixture_rows(
                matches=matches,
                competition_name=competition_name,
                competition_id=competition_id,
                season=SEASON,
            )

            print(
                f"Normalized: "
                f"{len(rows)} fixture(s)"
            )

            if not rows:

                raise RuntimeError(
                    f"{competition_name} produced "
                    f"zero usable fixtures. "
                    f"CSV files will not be updated."
                )

            all_rows.extend(rows)

        except OpenFootAPIError as exc:

            raise RuntimeError(
                f"Failed to fetch "
                f"{competition_name}: "
                f"{exc}"
            ) from exc

    # ---------------------------------------------------------
    # Global validation
    # ---------------------------------------------------------

    if not all_rows:

        raise RuntimeError(
            "OpenFoot returned zero usable fixtures "
            "across all competitions. "
            "CSV files will not be updated."
        )

    # ---------------------------------------------------------
    # Deduplicate by stable fixture ID
    # ---------------------------------------------------------

    unique_rows: dict[str, dict] = {}

    for row in all_rows:

        fixture_id = str(
            row.get("fixture_id") or ""
        ).strip()

        if not fixture_id:

            raise RuntimeError(
                "A normalized fixture is missing "
                "fixture_id."
            )

        unique_rows[
            fixture_id
        ] = row

    all_rows = list(
        unique_rows.values()
    )

    print()
    print("=" * 70)
    print(
        f"Total unique fixtures fetched: "
        f"{len(all_rows)}"
    )
    print("=" * 70)

    # ---------------------------------------------------------
    # 4. Update master CSV
    # ---------------------------------------------------------

    master_rows = (
        upsert_master_fixtures(
            new_rows=all_rows,
        )
    )

    print()
    print(
        f"Master CSV total fixtures: "
        f"{len(master_rows)}"
    )

    # ---------------------------------------------------------
    # 5. Generate Instagram CSV
    # ---------------------------------------------------------

    write_instagram_csv(
        master_rows=master_rows,
    )

    # ---------------------------------------------------------
    # Complete
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
