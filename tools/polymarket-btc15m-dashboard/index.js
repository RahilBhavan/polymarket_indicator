/**
 * Optional console dashboard: polls CryptoSignal API /api/15m-snapshot and
 * /api/live-data, renders a static screen. Does not copy external repo code;
 * data comes from our FastAPI app.
 *
 * Usage:
 *   Set CRYPTOSIGNAL_API_URL (default http://localhost:8000)
 *   Set CRYPTOSIGNAL_CRON_SECRET if your app requires X-Cron-Secret for /api/*
 *   bun run start
 */

const POLL_MS = 2000;
const API_URL = process.env.CRYPTOSIGNAL_API_URL || "http://localhost:8000";
const CRON_SECRET = process.env.CRYPTOSIGNAL_CRON_SECRET || "";

function headers() {
  const h = { "Content-Type": "application/json" };
  if (CRON_SECRET) h["X-Cron-Secret"] = CRON_SECRET;
  return h;
}

async function fetch15mSnapshot() {
  try {
    const r = await fetch(`${API_URL}/api/15m-snapshot`, { headers: headers() });
    if (!r.ok) return { ok: false, error: r.status };
    return await r.json();
  } catch (e) {
    return { ok: false, error: e?.message || String(e) };
  }
}

async function fetchLiveData() {
  try {
    const r = await fetch(`${API_URL}/api/live-data`, { headers: headers() });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

function screenWidth() {
  const w = process.stdout?.columns;
  return Number.isFinite(w) && w >= 40 ? w : 80;
}

function sep(ch = "─") {
  return ch.repeat(screenWidth());
}

function render(lines) {
  try {
    process.stdout.cursorTo(0, 0);
    process.stdout.clearScreenDown();
  } catch (_) {}
  process.stdout.write(lines.join("\n") + "\n");
}

function fmtNum(x) {
  if (x == null || typeof x !== "number" || Number.isNaN(x)) return "-";
  return x.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function fmtPct(x) {
  if (x == null || typeof x !== "number" || Number.isNaN(x)) return "-";
  return (x * 100).toFixed(1) + "%";
}

async function main() {
  while (true) {
    const [snap, live] = await Promise.all([fetch15mSnapshot(), fetchLiveData()]);

    const lines = [];
    lines.push("BTC 15m Dashboard (CryptoSignal API)");
    lines.push(sep());
    lines.push("");

    if (!snap?.ok) {
      lines.push("15m snapshot: " + (snap?.reason || snap?.error || "unavailable"));
      lines.push("Ensure the CryptoSignal app is running and " + API_URL + " is reachable.");
      if (CRON_SECRET) lines.push("X-Cron-Secret is set.");
      render(lines);
      await new Promise((r) => setTimeout(r, POLL_MS));
      continue;
    }

    const m = snap.market || {};
    const q = snap.quote || {};
    const sig = snap.last_signal || {};

    lines.push("Market: " + (m.slug || "-"));
    lines.push("Condition: " + (m.condition_id || "-").slice(0, 16) + "...");
    lines.push("End: " + (m.end_date || "-"));
    lines.push("Time left: " + (m.remaining_minutes != null ? m.remaining_minutes.toFixed(1) + "m" : "-"));
    lines.push("");
    lines.push(sep());
    lines.push("Quote (Up / Down)");
    lines.push("  Buy price: " + fmtNum(q.up_buy_price) + " / " + fmtNum(q.down_buy_price));
    lines.push("  Market norm: " + fmtPct(q.market_up_norm) + " / " + fmtPct(q.market_down_norm));
    lines.push("  Max safe USD: " + fmtNum(q.max_safe_up_usd) + " / " + fmtNum(q.max_safe_down_usd));
    lines.push("");
    if (sig.direction) {
      lines.push(sep());
      lines.push("Last signal: " + sig.direction + " | Model P: " + fmtPct(sig.model_p) + " | Edge: " + fmtPct(sig.edge) + " | Rec: $" + fmtNum(sig.recommended_usd));
      if (sig.run_at) lines.push("  At: " + sig.run_at);
    }
    if (live?.sources?.length) {
      lines.push("");
      lines.push(sep());
      lines.push("Live data (sample)");
      for (const s of live.sources.slice(0, 5)) {
        lines.push("  " + s.source_id + ": " + (s.raw_value ?? s.error ?? "-") + (s.normalized_score != null ? " → " + fmtNum(s.normalized_score) : ""));
      }
    }
    lines.push("");
    lines.push(sep());
    lines.push("Poll: " + API_URL + " every " + POLL_MS / 1000 + "s. Ctrl+C to exit.");

    render(lines);
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
