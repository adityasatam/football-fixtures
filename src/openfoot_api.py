import os
import time
from typing import Any

import requests

from .config import API_BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT_SECONDS


class OpenFootAPIError(RuntimeError):
    pass


class OpenFootClient:
    def __init__(self, api_key: str):
        api_key = api_key.strip()

        if not api_key:
            raise OpenFootAPIError("OPENFOOT_API_KEY is missing.")

        # OpenFoot keys should be plain ASCII.
        try:
            api_key.encode("ascii")
        except UnicodeEncodeError as exc:
            raise OpenFootAPIError(
                "OPENFOOT_API_KEY contains non-ASCII characters. "
                "Re-create the GitHub secret by copying only the API key "
                "starting with 'of_live_' without quotes or spaces."
            ) from exc

        if not api_key.startswith("of_live_"):
            raise OpenFootAPIError(
                "OPENFOOT_API_KEY does not start with 'of_live_'. "
                "Check that the correct OpenFoot API key was added to GitHub Secrets."
            )

        self.api_key = api_key

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
        )

    def get_matches(
        self,
        competition_id: str,
        season: str,
    ) -> list[dict[str, Any]]:

        params = {
            "competition": competition_id,
            "season": season,
        }

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
                    "UnicodeEncodeError while sending the OpenFoot request. "
                    "This almost certainly means OPENFOOT_API_KEY contains "
                    "an invalid/non-ASCII character. Re-create the GitHub "
                    "secret using the raw API key only."
                ) from exc

            except requests.RequestException as exc:

                if attempt < MAX_RETRIES:
                    sleep_seconds = 2 ** (attempt - 1)

                    print(
                        f"Network error: {exc}. "
                        f"Retrying in {sleep_seconds}s..."
                    )

                    time.sleep(sleep_seconds)
                    continue

                raise OpenFootAPIError(
                    f"Network error after {MAX_RETRIES} attempts: {exc}"
                ) from exc

            try:
                payload = response.json()
            except ValueError:
                payload = {}

            if response.ok:

                data = payload.get("data", [])

                if not isinstance(data, list):
                    raise OpenFootAPIError(
                        f"Unexpected response shape for "
                        f"{competition_id}: data is not a list."
                    )

                unavailable = payload.get("meta", {}).get("unavailable")

                if unavailable:
                    print(
                        f"WARNING: OpenFoot marked {competition_id} "
                        f"as unavailable: {unavailable}"
                    )

                return data

            error = payload.get("error", {})

            if not isinstance(error, dict):
                error = {}

            code = error.get("code", "unknown_error")
            message = error.get(
                "message",
                response.text[:500],
            )

            # Retry temporary failures.
            if response.status_code in (429, 502, 503, 504):

                if attempt < MAX_RETRIES:

                    sleep_seconds = 2 ** (attempt - 1)

                    print(
                        f"OpenFoot temporary error "
                        f"{response.status_code} ({code}). "
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
            f"Unable to fetch {competition_id}."
        )
