# Deploy CryptoSignal with Render + Neon (Free Tier)

Step-by-step guide to run the bot on **Render** (Web Service) and **Neon** (PostgreSQL) for free.

**Quick links:** [Neon](https://neon.tech) · [Render](https://render.com) · [cron-job.org](https://cron-job.org) (for scheduled jobs)

---

## Prerequisites

- GitHub account (for Render)
- [Neon](https://neon.tech) account
- [Render](https://render.com) account
- Your `.env` values: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_ALLOWED_USER_IDS`, and a new `EOD_CRON_SECRET` for production

---

## Part 1: Neon (PostgreSQL)

1. **Sign up** at [neon.tech](https://neon.tech) and log in.

2. **Create a project**
   - **New Project** → choose a name (e.g. `cryptosignal`) and region (pick one close to your Render region, e.g. Oregon/US West).
   - Click **Create project**.

3. **Get the connection string**
   - On the project **Dashboard**, open **Connection details**.
   - Copy the connection string. It looks like:
     ```
     postgresql://USER:PASSWORD@ep-xxx-xxx.region.aws.neon.tech/neondb?sslmode=require
     ```
   - Neon uses `neondb` as the default database name; that’s fine. Keep this URL for Render env (Step 5) and for running migrations (Step 4).

4. **Run schema and migrations (from your machine)**
   - Set `DATABASE_URL` to the Neon connection string and run the init script:
     ```bash
     cd cryptosignal
     export DATABASE_URL="postgresql://USER:PASSWORD@ep-xxx.region.aws.neon.tech/neondb?sslmode=require"
     uv run python scripts/init_db.py
     ```
   - If you prefer not to export, create a temporary `.env.deploy` with only `DATABASE_URL=...` and run:
     ```bash
     set -a && source .env.deploy && set +a && uv run python scripts/init_db.py
     ```
   - You should see migrations applied. The app will use this same `DATABASE_URL` on Render.

---

## Part 2: Render (Web Service)

1. **Push your code**  
   Ensure the `cryptosignal` app is in a GitHub repo (either the repo root is `cryptosignal` or the repo contains `cryptosignal` as a subdirectory).

2. **Create a Web Service on Render**
   - Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**.
   - **Connect** the GitHub repo that contains CryptoSignal.
   - **Optional – Blueprint:** If your **repo root is the cryptosignal folder** (only this project in the repo), you can use **New + → Blueprint** and point Render at the repo; it will read `render.yaml` and create the web service. You’ll be prompted for `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_ALLOWED_USER_IDS`, and `EOD_CRON_SECRET`. Then skip to Step 5 and add `ADMIN_CHAT_ID` in the dashboard if you want.
   - Otherwise, continue with manual setup below.

3. **Configure the service (manual setup)**
   - **Name:** e.g. `cryptosignal`.
   - **Region:** choose one (e.g. Oregon); same region as Neon is better for latency.
   - **Root Directory** (important):
     - If the repo root **is** the cryptosignal app (only this project in the repo), leave blank.
     - If the repo contains multiple projects and cryptosignal is in a subfolder, set **Root Directory** to that folder (e.g. `cryptosignal`).
   - **Runtime:** **Docker**.
   - **Dockerfile Path:** `docker/Dockerfile` (relative to Root Directory).
   - **Docker Context:** leave default (build context = Root Directory).
   - **Instance Type:** **Free**.

4. **Environment variables**  
   In **Environment** → **Add Environment Variable**, add:

   | Key | Value |
   |-----|--------|
   | `DATABASE_URL` | Your Neon connection string (from Part 1, Step 3) |
   | `TELEGRAM_BOT_TOKEN` | From your `.env` |
   | `TELEGRAM_WEBHOOK_SECRET` | From your `.env` |
   | `TELEGRAM_ALLOWED_USER_IDS` | From your `.env` (comma-separated IDs) |
   | `EOD_CRON_SECRET` | New secret for production, e.g. `openssl rand -hex 32` |
   | `ADMIN_CHAT_ID` | (Optional) Your Telegram ID for alerts |

   Do **not** add `.env` file to the repo; use Render’s env only.

5. **Deploy**
   - Click **Create Web Service**. Render will build the Docker image and deploy.
   - Wait for the first deploy to finish. The service URL will be like:
     `https://cryptosignal-xxxx.onrender.com`

6. **Health check**
   ```bash
   curl https://YOUR-SERVICE-NAME.onrender.com/health
   ```
   You should get `200` and JSON with `"status":"ok"` and `"db":"connected"`.

---

## Part 3: Telegram webhook

Set Telegram to send updates to your Render URL:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://YOUR-SERVICE-NAME.onrender.com/webhook/telegram" \
  -d "secret_token=<YOUR_TELEGRAM_WEBHOOK_SECRET>"
```

Replace:
- `YOUR_TELEGRAM_BOT_TOKEN` → value from Render env.
- `YOUR-SERVICE-NAME` → your Render service name (from the URL).
- `YOUR_TELEGRAM_WEBHOOK_SECRET` → value from Render env.

Verify:

```bash
curl "https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

You should see `"url":"https://YOUR-SERVICE-NAME.onrender.com/webhook/telegram"`.

---

## Part 4: Cron jobs (optional but recommended)

Render’s free tier does not include cron. Use an external free scheduler (e.g. [cron-job.org](https://cron-job.org)) to call your internal endpoints.

1. **Sign up** at [cron-job.org](https://cron-job.org) and create a cron job.

2. **Daily signal** (e.g. once per day, e.g. 12:00 UTC)
   - **URL:** `https://YOUR-SERVICE-NAME.onrender.com/internal/run-daily-signal`
   - **Method:** POST
   - **Request headers:**  
     `X-Cron-Secret: <YOUR_EOD_CRON_SECRET>`
   - **Schedule:** e.g. daily at 12:00 UTC.

3. **EOD outcomes** (e.g. after midnight UTC)
   - **URL:** `https://YOUR-SERVICE-NAME.onrender.com/internal/run-eod-outcomes`
   - **Method:** POST
   - **Request headers:**  
     `X-Cron-Secret: <YOUR_EOD_CRON_SECRET>`
   - **Schedule:** e.g. daily at 00:30 UTC.

Use the same `EOD_CRON_SECRET` you set in Render.

---

## Free tier notes

- **Render:** Free web services spin down after ~15 minutes of no traffic. The first request (e.g. a Telegram update or cron) may take 30–60 seconds while the service starts. After that, responses are fast until the next spin-down.
- **Neon:** Free tier has limits (e.g. compute hours, storage). See [Neon pricing](https://neon.tech/docs/introduction/usage-based-pricing) for current limits.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Build fails on Render | Ensure **Root Directory** and **Dockerfile Path** are correct. Build context must include `src/`, `pyproject.toml`, `uv.lock`, and `docker/Dockerfile`. |
| `/health` returns 503 or DB error | Verify `DATABASE_URL` in Render env: correct Neon URL, `?sslmode=require` if Neon requires SSL. Re-run `scripts/init_db.py` against that URL. |
| Telegram not receiving updates | Confirm webhook is set (`getWebhookInfo`). Ensure Render URL is HTTPS and the service has finished deploying. Check Render **Logs** for webhook errors. |
| Cron returns 401 | Add header `X-Cron-Secret` with the exact `EOD_CRON_SECRET` value from Render env. |

For more: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) and [runbook.md](runbook.md).

---

## Monorepo (cryptosignal in a subfolder)

If your Git repo root is a parent folder (e.g. `indicator`) and `cryptosignal` is a subdirectory:

- **Manual:** When creating the Web Service, set **Root Directory** to `cryptosignal` (or the path to the app folder). Set **Dockerfile Path** to `docker/Dockerfile`. Add env vars as in Part 2.
- **Blueprint:** Put a `render.yaml` at the **repo root** with `rootDir: cryptosignal` and `dockerfilePath: ./cryptosignal/docker/Dockerfile`, `dockerContext: ./cryptosignal`, or use manual setup.
