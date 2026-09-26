import time
from datetime import date
from typing import Any

import requests

from .config import (
    API_BASE_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
)


class OpenFootAPIError(RuntimeError):
    pass


class OpenFootClient:
    def __init__(self, api_key: str):
        api_key = api_key.strip()

        if not api_key:
            raise OpenFootAPIError(
                "OPENFOOT_API_KEY is missing."
            )

        try:
            api_key.encode("ascii")
        except UnicodeEncodeError as exc:
            raise OpenFootAPIError(
                "OPENFOOT_API_KEY contains non-ASCII characters. "
                "Re-create the GitHub secret by copying only the "
                "raw API key."
            ) from exc

        if not api_key.startswith("of_live_"):
            raise OpenFootAPIError(
                "OPENFOOT_API_KEY does not start with 'of_live_'. "
                "Check the GitHub Actions secret."
            )

        self.api_key = api_key

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
        )

    # -----------------------------------------------------
    # Generic request
    # -----------------------------------------------------

    def _request_matches(
        self,
        params: dict[str, str],
        description: str,
    ) -> list[dict[str, Any]]:

        url = f"{API_BASE_URL}/matches"

        for attempt in range(1, MAX_RETRIES + 1):

            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

            except UnicodeEncodeError as exc:
                raise OpenFootAPIError(
                    "UnicodeEncodeError while sending the OpenFoot "
                    "request. Check OPENFOOT_API_KEY."
                ) from exc

            except requests.RequestException as exc:

                if attempt < MAX_RETRIES:
                    sleep_seconds = 2 ** (attempt - 1)

                    print(
                        f"Network error while fetching "
                        f"{description}: {exc}"
                    )

                    print(
                        f"Retrying in {sleep_seconds}s..."
                    )

                    time.sleep(sleep_seconds)

                    continue

                raise OpenFootAPIError(
                    f"Network error after {MAX_RETRIES} attempts "
                    f"while fetching {description}: {exc}"
                ) from exc

            # -------------------------------------------------
            # Parse response
            # -------------------------------------------------

            try:
                payload = response.json()

            except ValueError:
                payload = {}

            # -------------------------------------------------
            # Successful response
            # -------------------------------------------------

            if response.ok:

                data = payload.get("data", [])

                if not isinstance(data, list):
                    raise OpenFootAPIError(
                        f"Unexpected OpenFoot response for "
                        f"{description}: data is not a list."
                    )

                meta = payload.get("meta", {})

                if not isinstance(meta, dict):
                    meta = {}

                unavailable = meta.get("unavailable")

                if unavailable:
                    print(
                        f"WARNING: OpenFoot marked "
                        f"{description} as unavailable: "
                        f"{unavailable}"
                    )

                print(
                    f"OpenFoot: {description} -> "
                    f"{len(data)} fixtures"
                )

                return data

            # -------------------------------------------------
            # Error response
            # -------------------------------------------------

            error = payload.get("error", {})

            if not isinstance(error, dict):
                error = {}

            code = error.get(
                "code",
                "unknown_error",
            )

            message = error.get(
                "message",
                response.text[:500],
            )

            # -------------------------------------------------
            # Retry temporary errors
            # -------------------------------------------------

            if response.status_code in (
                429,
                502,
                503,
                504,
            ):

                if attempt < MAX_RETRIES:

                    sleep_seconds = 2 ** (attempt - 1)

                    print(
                        f"OpenFoot temporary error "
                        f"{response.status_code} "
                        f"({code}) while fetching "
                        f"{description}."
                    )

                    print(
                        f"Retrying in {sleep_seconds}s..."
                    )

                    time.sleep(sleep_seconds)

                    continue

            raise OpenFootAPIError(
                f"OpenFoot API error "
                f"{response.status_code}: "
                f"{code}: {message}"
            )

        raise OpenFootAPIError(
            f"Unable to fetch {description}."
        )

    # -----------------------------------------------------
    # Season-level request
    # -----------------------------------------------------

    def get_matches(
        self,
        competition_id: str,
        season: str,
    ) -> list[dict[str, Any]]:

        return self._request_matches(
            params={
                "competition": competition_id,
                "season": season,
            },
            description=(
                f"{competition_id} "
                f"season {season}"
            ),
        )

    # -----------------------------------------------------
    # Exact date request
    # -----------------------------------------------------

    def get_matches_for_date(
        self,
        competition_id: str,
        season: str,
        match_date: date,
    ) -> list[dict[str, Any]]:

        date_string = match_date.isoformat()

        return self._request_matches(
            params={
                "competition": competition_id,
                "season": season,
                "date": date_string,
            },
            description=(
                f"{competition_id} "
                f"season {season} "
                f"date {date_string}"
            ),
        )
