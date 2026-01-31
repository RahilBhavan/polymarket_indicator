# Google Sheets template

## Sheet 1: Daily Signals

| Column | Type   | Description        |
|--------|--------|--------------------|
| A: Date | Date   | Signal date        |
| B: Timestamp | DateTime | Generation time |
| C: Asset | String | BTC                |
| D: Direction | YES/NO/NO_TRADE |
| E: Confidence | %     | Model confidence   |
| F: Model_P | Float  |                    |
| G: Market_P | Float |                    |
| H: Edge | Float  |                    |
| I: Recommended USD | Float |
| J: Outcome | WIN/LOSS/SKIP |
| K: Result | WIN/LOSS/SKIP |
| L: Status | ok/partial/error |

Create a sheet named "Daily Signals" with headers in row 1. Sync appends rows.

## Optional: Sheet 2 – Performance Summary

Formulas or manual: Total signals, Wins, Losses, Win rate, Streak.

## Env

- `GOOGLE_APPLICATION_CREDENTIALS`: path to service account JSON
- `SPREADSHEET_ID`: spreadsheet ID from URL
