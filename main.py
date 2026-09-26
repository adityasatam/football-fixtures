import csv
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# ============================================================
# CONFIGURATION
# ============================================================

CSV_URL = (
    "https://raw.githubusercontent.com/"
    "adityasatam/football-fixtures/main/"
    "data/instagram_fixtures.csv"
)

TIMEZONE = "Asia/Kolkata"
LOOKBACK_DAYS = 1

# Resolve all files relative to main.py
BASE_DIR = Path(__file__).resolve().parent

MASTER_PROMPT_FILE = BASE_DIR / "master_prompt.txt"
PROMPT_REFERENCE_FILE = BASE_DIR / "prompt_ref.txt"
PROMPTS_DIRECTORY = BASE_DIR / "prompts"


# ============================================================
# DATE HELPERS
# ============================================================

def get_today_ist():
    """Return today's date in IST."""
    return datetime.now(
        ZoneInfo(TIMEZONE)
    ).date()


def get_date_range():
    """
    Return the last 5 calendar days including today.

    Example:
        Today = 25 Sep 2026
        Range = 21 Sep 2026 -> 25 Sep 2026
    """

    today = get_today_ist()

    start_date = today - timedelta(
        days=LOOKBACK_DAYS - 1
    )

    return start_date, today


def format_match_date(date_string):
    """
    Convert:
        2026-09-19

    Into:
        19th Sep 2026
    """

    match_date = datetime.strptime(
        date_string,
        "%Y-%m-%d"
    ).date()

    day = match_date.day

    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(day % 10, "th")

    return (
        f"{day}{suffix} "
        f"{match_date.strftime('%b %Y')}"
    )


# ============================================================
# CAPTION HELPERS
# ============================================================

def normalize_instagram_caption(caption):
    """
    Convert the Instagram caption into one physical line.

    Newlines, tabs and repeated whitespace are replaced
    with a single space.
    """

    return re.sub(
        r"\s+",
        " ",
        caption
    ).strip()


# ============================================================
# FILE HELPERS
# ============================================================

def read_master_prompt():
    """Read the complete master prompt."""

    if not MASTER_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Required file not found: "
            f"{MASTER_PROMPT_FILE}"
        )

    return MASTER_PROMPT_FILE.read_text(
        encoding="utf-8"
    ).strip()


def read_prompt_references():
    """
    Read prompt_ref.txt.

    Each line contains ONLY the generated prompt filename.

    Example:
        Premier_League_Spurs_vs_Aston_Villa_19_Sep_2026.txt
    """

    if not PROMPT_REFERENCE_FILE.exists():
        PROMPT_REFERENCE_FILE.touch()

    references = set()

    with PROMPT_REFERENCE_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:
            filename = line.strip()

            if filename:
                references.add(filename)

    return references


def add_to_prompt_reference(filename):
    """
    Append the successfully-created prompt filename
    to prompt_ref.txt.
    """

    with PROMPT_REFERENCE_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            filename + "\n"
        )


# ============================================================
# CSV HELPERS
# ============================================================

def fetch_fixtures():
    """Download and parse the football fixtures CSV."""

    response = requests.get(
        CSV_URL,
        timeout=30
    )

    response.raise_for_status()

    csv_content = response.content.decode(
        "utf-8-sig"
    )

    reader = csv.DictReader(
        io.StringIO(csv_content)
    )

    return list(reader)


def get_recent_finished_fixtures(fixtures):
    """
    Get finished matches from the last 5 calendar days
    including today, based on IST.
    """

    start_date, end_date = get_date_range()

    recent_fixtures = []

    for fixture in fixtures:

        status = fixture.get(
            "status",
            ""
        ).strip().lower()

        if status != "finished":
            continue

        match_date_string = fixture.get(
            "match_date",
            ""
        ).strip()

        if not match_date_string:
            continue

        try:
            match_date = datetime.strptime(
                match_date_string,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            continue

        if start_date <= match_date <= end_date:
            recent_fixtures.append(
                fixture
            )

    # Process oldest → newest
    recent_fixtures.sort(
        key=lambda x: x.get(
            "match_date",
            ""
        )
    )

    return recent_fixtures


# ============================================================
# MATCH / FILENAME HELPERS
# ============================================================

def create_match_reference(fixture):
    """
    Create the first line of the individual prompt file.

    Example:
        Premier League | Spurs vs Aston Villa | 19th Sep 2026
    """

    competition = fixture.get(
        "competition",
        ""
    ).strip()

    home_team = fixture.get(
        "home_team",
        ""
    ).strip()

    away_team = fixture.get(
        "away_team",
        ""
    ).strip()

    match_date = fixture.get(
        "match_date",
        ""
    ).strip()

    formatted_date = format_match_date(
        match_date
    )

    return (
        f"{competition} | "
        f"{home_team} vs {away_team} | "
        f"{formatted_date}"
    )


def sanitize_filename(text):
    """
    Make text safe for use in a Windows/Linux filename.
    """

    # Remove non-ASCII characters such as emojis
    text = text.encode(
        "ascii",
        "ignore"
    ).decode()

    # Remove Windows-invalid filename characters
    invalid_characters = '<>:"/\\|?*'

    for char in invalid_characters:
        text = text.replace(
            char,
            ""
        )

    # Replace whitespace with underscores
    text = "_".join(
        text.split()
    )

    # Keep only safe characters
    text = "".join(
        char
        for char in text
        if char.isalnum()
        or char in ("_", "-")
    )

    # Collapse repeated underscores
    text = re.sub(
        r"_+",
        "_",
        text
    )

    return text.strip(
        "_-"
    )


def create_prompt_filename(fixture):
    """
    Create a short, clean filename based on:

        Competition
        Home team
        Away team
        Match date

    Example:
        LaLiga_Espanyol_vs_Levante_16_Aug_2026.txt
    """

    competition = fixture.get(
        "competition",
        ""
    ).strip()

    home_team = fixture.get(
        "home_team",
        ""
    ).strip()

    away_team = fixture.get(
        "away_team",
        ""
    ).strip()

    match_date_string = fixture.get(
        "match_date",
        ""
    ).strip()

    match_date = datetime.strptime(
        match_date_string,
        "%Y-%m-%d"
    ).date()

    formatted_date = match_date.strftime(
        "%d_%b_%Y"
    )

    filename_base = (
        f"{competition}_"
        f"{home_team}_vs_{away_team}_"
        f"{formatted_date}"
    )

    filename_base = sanitize_filename(
        filename_base
    )

    return f"{filename_base}.txt"


# ============================================================
# VALIDATION
# ============================================================

def validate_fixture(fixture):
    """
    Verify that all fields required to create a prompt
    are available.
    """

    required_fields = [
        "competition",
        "home_team",
        "away_team",
        "match_date",
        "status",
        "instagram_caption",
    ]

    missing_fields = []

    for field in required_fields:

        value = fixture.get(
            field,
            ""
        ).strip()

        if not value:
            missing_fields.append(
                field
            )

    if missing_fields:
        return False, missing_fields

    return True, []


# ============================================================
# PROMPT CREATION
# ============================================================

def create_prompt_file(
    fixture,
    master_prompt
):
    """
    Create the individual match prompt.

    Structure:

        League | Home vs Away | Date

        instagram_caption="one-line caption"

        complete master_prompt.txt
    """

    PROMPTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    filename = create_prompt_filename(
        fixture
    )

    prompt_file = (
        PROMPTS_DIRECTORY / filename
    )

    # Never overwrite an existing prompt file.
    if prompt_file.exists():
        return None, filename, "exists"

    match_reference = create_match_reference(
        fixture
    )

    instagram_caption = normalize_instagram_caption(
        fixture.get(
            "instagram_caption",
            ""
        )
    )

    prompt_content = (
        f"{match_reference}\n\n"
        f'instagram_caption="{instagram_caption}"\n\n'
        f"{master_prompt}\n"
    )

    prompt_file.write_text(
        prompt_content,
        encoding="utf-8"
    )

    return (
        prompt_file,
        filename,
        "created"
    )


# ============================================================
# MAIN PROCESSING
# ============================================================

def process_fixtures():

    # --------------------------------------------------------
    # Read master prompt
    # --------------------------------------------------------

    master_prompt = read_master_prompt()

    # --------------------------------------------------------
    # Read permanent filename log
    # --------------------------------------------------------

    processed_files = read_prompt_references()

    # --------------------------------------------------------
    # Fetch CSV
    # --------------------------------------------------------

    fixtures = fetch_fixtures()

    # --------------------------------------------------------
    # Filter last 5 days + finished
    # --------------------------------------------------------

    recent_fixtures = get_recent_finished_fixtures(
        fixtures
    )

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    created_count = 0
    skipped_processed_count = 0
    skipped_existing_count = 0
    invalid_count = 0

    # --------------------------------------------------------
    # Process matches
    # --------------------------------------------------------

    for fixture in recent_fixtures:

        # Validate fixture
        is_valid, missing_fields = validate_fixture(
            fixture
        )

        if not is_valid:
            invalid_count += 1
            continue

        # Generate expected filename
        filename = create_prompt_filename(
            fixture
        )

        # ----------------------------------------------------
        # Check permanent filename log
        # ----------------------------------------------------

        if filename in processed_files:

            skipped_processed_count += 1
            continue

        # ----------------------------------------------------
        # Create individual prompt file
        # ----------------------------------------------------

        prompt_file, created_filename, status = (
            create_prompt_file(
                fixture,
                master_prompt
            )
        )

        # ----------------------------------------------------
        # Existing prompt file but not in log
        # ----------------------------------------------------

        if status == "exists":

            skipped_existing_count += 1
            continue

        # ----------------------------------------------------
        # Only log filename AFTER successful creation
        # ----------------------------------------------------

        add_to_prompt_reference(
            created_filename
        )

        processed_files.add(
            created_filename
        )

        created_count += 1

    # --------------------------------------------------------
    # Final summary ONLY
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)

    print(
        f"Matches checked               : "
        f"{len(recent_fixtures)}"
    )

    print(
        f"New prompts created           : "
        f"{created_count}"
    )

    print(
        f"Already in prompt_ref.txt     : "
        f"{skipped_processed_count}"
    )

    print(
        f"Existing prompt files skipped : "
        f"{skipped_existing_count}"
    )

    print(
        f"Invalid fixtures skipped      : "
        f"{invalid_count}"
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        process_fixtures()

    except requests.RequestException as error:

        print()
        print("ERROR: Unable to fetch fixtures CSV.")
        print(error)

    except FileNotFoundError as error:

        print()
        print("ERROR: Required file not found.")
        print(error)

    except Exception as error:

        print()
        print("ERROR: Unexpected error occurred.")
        print(error)
