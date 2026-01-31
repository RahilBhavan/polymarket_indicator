# Git Setup and Deploy to Render

Short checklist to get the project under Git and deploy to Render.

---

## 1. Git (repo already at parent `indicator/`)

If you're working from the **indicator** repo (cryptosignal is a subfolder):

- The repo root is `indicator/`. Render will use **Root Directory** `cryptosignal` (or Blueprint will read `render.yaml` at repo root).
- Ensure **no secrets** are committed:
  - `.env` and `.env.*` are in `.gitignore` (only `.env.example` is tracked).
  - Never commit `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, or other secrets.

**First-time push (if not already pushed):**

```bash
cd /path/to/indicator
git add .
git status   # confirm no .env or .env.* listed
git commit -m "Add cryptosignal app and Render Blueprint"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git   # if needed
git push -u origin main
```

---

## 2. Render (connect repo and deploy)

1. **Dashboard**  
   Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Web Service**.

2. **Connect repo**  
   Connect the GitHub (or GitLab/Bitbucket) repo that contains **indicator** (with `cryptosignal` inside).

3. **Use Blueprint (recommended)**  
   - **New +** → **Blueprint** → select the same repo.  
   - Render will read `render.yaml` at the **repo root** (`indicator/render.yaml`), which sets `rootDir: cryptosignal`.  
   - You’ll be prompted for env vars; add them (see step 4).

   **Or manual:**  
   - Create a **Web Service**, same repo.  
   - **Root Directory:** `cryptosignal`.  
   - **Runtime:** Docker.  
   - **Dockerfile path:** `docker/Dockerfile`.  
   - **Docker context:** `.` (relative to Root Directory).

4. **Environment variables**  
   In Render → **Environment**, add (do **not** commit these):

   | Key | Value |
   |-----|--------|
   | `DATABASE_URL` | Neon (or other PostgreSQL) URL, e.g. `postgresql://...?sslmode=require` |
   | `TELEGRAM_BOT_TOKEN` | From BotFather |
   | `TELEGRAM_WEBHOOK_SECRET` | e.g. `openssl rand -hex 32` |
   | `TELEGRAM_ALLOWED_USER_IDS` | Comma-separated Telegram user IDs |
   | `EOD_CRON_SECRET` | e.g. `openssl rand -hex 32` (for cron endpoints) |
   | `ADMIN_CHAT_ID` | (Optional) Your Telegram ID for alerts |

5. **Deploy**  
   Create the service. After deploy, test:

   ```bash
   curl https://YOUR-SERVICE-NAME.onrender.com/health
   ```

   Then set the Telegram webhook and optional cron jobs as in [DEPLOY_RENDER_NEON.md](DEPLOY_RENDER_NEON.md).

---

## 3. Standalone repo (cryptosignal only)

If you want a **separate** Git repo that contains only cryptosignal (repo root = cryptosignal):

```bash
cd /path/to/indicator/cryptosignal
git init
git add .
git status   # confirm no .env
git commit -m "Initial commit: cryptosignal app"
git remote add origin https://github.com/YOUR_USER/cryptosignal.git
git push -u origin main
```

On Render, connect this repo and leave **Root Directory** blank (or use the existing `cryptosignal/render.yaml` via Blueprint from that repo).

---

## Summary

| Repo layout | Render Root Directory | Blueprint |
|-------------|------------------------|-----------|
| indicator/ (cryptosignal inside) | `cryptosignal` | Use `indicator/render.yaml` at repo root |
| cryptosignal/ only | (blank) | Use `cryptosignal/render.yaml` |

Full deploy steps (Neon DB, migrations, webhook, cron): [DEPLOY_RENDER_NEON.md](DEPLOY_RENDER_NEON.md).
