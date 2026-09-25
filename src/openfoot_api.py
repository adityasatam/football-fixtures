import os
import time
from typing import Any

import requests

from .config import API_BASE_URL, MAX_RETRIES, REQUEST_TIMEOUT_SECONDS


class OpenFootAPIError(RuntimeError):
    pass


class OpenFootClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise OpenFootAPIError("OPENFOOT_API_KEY is missing.")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "football-fixtures-github-action/1.0",
            }
        )

    def get_matches(self, competition_id: str, season: str) -> list[dict[str, Any]]:
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

                try:
                    payload = response.json()
                except ValueError:
                    payload = {}

                if response.ok:
                    data = payload.get("data", [])
                    if not isinstance(data, list):
                        raise OpenFootAPIError(
                            f"Unexpected response shape for {competition_id}: data is not a list."
                        )
                    return data

                error = payload.get("error", {})
                code = error.get("code", "unknown_error")
                message = error.get("message", response.text[:500])

                # Retry transient source/server/rate-limit errors.
                if response.status_code in (429, 502, 503, 504) and attempt < MAX_RETRIES:
                    sleep_seconds = 2 ** (attempt - 1)
                    print(
                        f"OpenFoot temporary error {response.status_code} ({code}). "
                        f"Retrying in {sleep_seconds}s..."
                    )
                    time.sleep(sleep_seconds)
                    continue

                raise OpenFootAPIError(
                    f"OpenFoot API error {response.status_code}: {code}: {message}"
                )

            except requests.RequestException as exc:
                if attempt < MAX_RETRIES:
                    sleep_seconds = 2 ** (attempt - 1)
                    print(f"Network error: {exc}. Retrying in {sleep_seconds}s...")
                    time.sleep(sleep_seconds)
                    continue
                raise OpenFootAPIError(f"Network error after {MAX_RETRIES} attempts: {exc}") from exc

        raise OpenFootAPIError(f"Unable to fetch {competition_id}.")
