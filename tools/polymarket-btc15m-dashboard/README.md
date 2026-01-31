# Polymarket BTC 15m Dashboard (optional)

Optional console dashboard that polls the **CryptoSignal** FastAPI app for the BTC 15m snapshot and live data, and renders a static screen. It does **not** copy code from any external repo; all data comes from our API.

## Requirements

- [Bun](https://bun.sh/) (or Node 18+)
- CryptoSignal app running (e.g. `uv run uvicorn app.main:app --reload`)

## Usage

1. Start the CryptoSignal app (see project root README).
2. From this directory:
   ```bash
   bun run start
   ```
   Or with custom API URL and secret:
   ```bash
   CRYPTOSIGNAL_API_URL=http://localhost:8000 CRYPTOSIGNAL_CRON_SECRET=your_secret bun run start
   ```

## Environment variables

| Variable | Description |
|----------|-------------|
| `CRYPTOSIGNAL_API_URL` | Base URL of the CryptoSignal API (default: `http://localhost:8000`) |
| `CRYPTOSIGNAL_CRON_SECRET` | If your app requires `X-Cron-Secret` for `/api/*`, set it here |

## Endpoints used

- `GET /api/15m-snapshot` – current BTC 15m market, quote, remaining minutes, last signal
- `GET /api/live-data` – optional; fetcher snapshot (sources and normalized scores)

Press Ctrl+C to exit.
