# Football Fixtures 2026/27

A small GitHub-ready Python project that maintains one CSV containing fixtures for exactly these 9 competitions:

1. Premier League
2. La Liga
3. Serie A
4. Bundesliga
5. Ligue 1
6. UEFA Champions League
7. UEFA Europa League
8. UEFA Conference League
9. UEFA Nations League

Data source: OpenFoot API.

## What it does

- Fetches the 2026/27 season fixture set for all 9 competitions.
- Converts kickoff timestamps from UTC to IST (`Asia/Kolkata`).
- Stores home/away teams, fixture status, venue and stable fixture ID.
- Upserts fixtures into one CSV.
- Runs automatically once per day with GitHub Actions.
- If a match is postponed/rescheduled and OpenFoot returns the changed kickoff/status, the existing CSV row is updated instead of duplicated.

## 1. Create an OpenFoot API key

Create a free Starter account/key from:

https://openfootapi.com/pricing

The free Starter plan currently provides 5,000 authenticated requests/month and access to the 120-competition catalog.

## 2. Add the GitHub secret

In your repository:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Name:

`OPENFOOT_API_KEY`

Value:

Your OpenFoot key, e.g. `of_live_...`

Do not put the real key in the repository.

## 3. Run locally

```bash
python -m venv .venv

# Windows
.venv\\Scripts\\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and put your key in it:

```text
OPENFOOT_API_KEY=of_live_your_key_here
```

Then run:

```bash
python -m src.main
```

## 4. Run from GitHub Actions

The workflow runs every day at 09:00 IST.

You can also run it manually:

`Actions -> Update football fixtures -> Run workflow`

## CSV

The output file is:

`data/football_fixtures_2026_27.csv`

Columns:

```text
fixture_id
competition
competition_id
season
date_ist
time_ist
datetime_ist
datetime_utc
home_team
home_team_id
away_team
away_team_id
status
venue
last_updated
```

## Request usage

The updater makes 9 season-level `/v1/matches` requests per run: one for each competition.

At one run per day, that is roughly 270 requests/month, comfortably below the current 5,000-request free monthly quota.

## Important source note

OpenFoot's documentation says `kickoffAt` is returned as an ISO-8601 UTC timestamp and supports filtering by stable competition ID and season. The coverage catalog currently lists all 9 requested competitions for 2026/27.

Coverage and upstream source availability can change, so the script intentionally fails loudly instead of silently writing an incomplete fixture file.
