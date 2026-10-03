```python
def _build_instagram_rows(
    master_rows: list[dict],
) -> list[dict]:
    """
    Create Instagram-friendly records from the master fixture data.

    IMPORTANT STATUS RULE
    ---------------------
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

    now_ist = datetime.now(IST)
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
        # Keep this as a calendar-day difference.
        #
        # Example:
        #   Today = 03 Oct
        #   Match = 01 Oct
        #   days_until_match = -2
        #
        # Negative values are intentional and useful for
        # identifying matches whose date has passed.
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
        # kickoff timestamp and already represents IST.
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
        # Only override scheduled.
        #
        # We DO NOT override:
        #   live
        #   finished
        #   postponed
        #   cancelled
        #   unknown
        #
        # This prevents us from accidentally changing an
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

        if effective_status == "scheduled":

            post_type = "MATCH_PREVIEW"

        elif effective_status == "postponed":

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

        tomorrow = (
            today.fromordinal(
                today.toordinal() + 1
            )
        )

        is_tomorrow = (
            match_date == tomorrow
            if match_date is not None
            else False
        )

        # ----------------------------------------------------
        # Instagram caption.
        #
        # Use the effective status rather than stale source
        # status so downstream logic sees the corrected state.
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

                "is_today": str(
                    is_today
                ).lower(),

                "is_tomorrow": str(
                    is_tomorrow
                ).lower(),

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
```
