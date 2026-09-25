import os
import sys

from dotenv import load_dotenv

from .config import COMPETITIONS, DATA_FILE, SEASON
from .fixtures import load_csv, save_csv, upsert_matches
from .openfoot_api import OpenFootAPIError, OpenFootClient


def main() -> int:
    load_dotenv()

    api_key = os.getenv("OPENFOOT_API_KEY", "").strip()
    if not api_key:
        print("OPENFOOT_API_KEY is missing.")
        return 1

    client = OpenFootClient(api_key)
    rows = load_csv(DATA_FILE)

    total_added = 0
    total_updated = 0
    total_fetched = 0

    print(f"Starting fixture sync for season {SEASON}...")
    print(f"Competitions: {len(COMPETITIONS)}")

    try:
        for competition_name, competition_id in COMPETITIONS.items():
            print(f"\nFetching {competition_name} ({competition_id})...")
            matches = client.get_matches(competition_id, SEASON)
            total_fetched += len(matches)

            added, updated = upsert_matches(
                rows,
                matches,
                competition_name,
                competition_id,
                SEASON,
            )

            total_added += added
            total_updated += updated

            print(
                f"  fetched={len(matches)} added={added} updated={updated} "
                f"total_rows={len(rows)}"
            )

    except (OpenFootAPIError, ValueError) as exc:
        print(f"\nSYNC FAILED: {exc}")
        return 1

    save_csv(DATA_FILE, rows)

    print("\nSync completed successfully.")
    print(f"Fetched: {total_fetched}")
    print(f"Added: {total_added}")
    print(f"Updated: {total_updated}")
    print(f"Rows in CSV: {len(rows)}")
    print(f"Output: {DATA_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
