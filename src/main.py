import os

from dotenv import load_dotenv

from .config import COMPETITIONS, SEASON
from .fixtures import (
    build_fixture_rows,
    upsert_master_fixtures,
    write_instagram_csv,
)
from .openfoot_api import OpenFootAPIError, OpenFootClient


def main() -> None:
    load_dotenv()

    api_key = os.getenv("OPENFOOT_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENFOOT_API_KEY environment variable is missing."
        )

    client = OpenFootClient(api_key)

    all_rows = []

    print("=" * 70)
    print("OPENFOOT FOOTBALL FIXTURE SYNC")
    print(f"Season: {SEASON}")
    print(f"Competitions: {len(COMPETITIONS)}")
    print("=" * 70)

    for competition_name, competition_id in COMPETITIONS.items():

        print(
            f"\nFetching: {competition_name} "
            f"({competition_id})"
        )

        try:
            matches = client.get_matches(
                competition_id=competition_id,
                season=SEASON,
            )

            print(
                f"  OpenFoot returned {len(matches)} matches"
            )

            rows = build_fixture_rows(
                matches=matches,
                competition_name=competition_name,
                competition_id=competition_id,
                season=SEASON,
            )

            print(
                f"  Normalised {len(rows)} matches"
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

    print("\n" + "=" * 70)
    print(f"Total fixtures fetched: {len(all_rows)}")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. Update master CSV
    # ---------------------------------------------------------

    master_rows = upsert_master_fixtures(
        new_rows=all_rows
    )

    print(
        f"\nMaster CSV updated with "
        f"{len(master_rows)} total fixtures."
    )

    # ---------------------------------------------------------
    # 2. Generate Instagram CSV
    # ---------------------------------------------------------

    write_instagram_csv(
        master_rows=master_rows
    )

    print("\n" + "=" * 70)
    print("SYNC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
