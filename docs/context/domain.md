# Domain: Polymarket & Signal Concepts

## Polymarket contract basics

- **Binary outcome**: Each contract settles to either **$1.00 (YES)** or **$0.00 (NO)**.
- **Price = implied probability**: A "Yes" share trading at **$0.65** means the market implies **65%** probability that the event occurs.
- **Resolution**: Defined per market (e.g. "Bitcoin closes above $96,500 at 23:59 UTC on Binance"). Resolution source (exchange, index) must match exactly for outcome recording.

## Core definitions

| Term | Definition |
|------|------------|
| **Model_P** | Bot's estimated probability (0.00–1.00) that the target outcome (e.g. "Green Day" / YES) occurs. Output of the signal engine. |
| **Market_P** | Market-implied probability. For buying YES: use best **ask** price. For NO: use `1 - best_bid` or equivalent. |
| **Edge** | `Edge = Model_P - Market_P`. Positive edge on YES means model thinks YES is underpriced; positive edge on NO means NO is underpriced. |
| **Fee-adjusted edge** | Edge minus estimated execution cost (taker fee + half-spread). Used to gate: only signal when fee-adjusted edge > threshold. |
| **NO_TRADE** | Decision when edge is below threshold or fee-adjusted edge is negative. User gets "No trade recommended" with reasoning. |

## Semantics for daily BTC markets

- **YES** = outcome occurs (e.g. "BTC closes above strike").
- **NO** = outcome does not occur.
- We compare Model_P to the **YES** side: if Model_P > Market_P_yes by enough, recommend buying YES; if Model_P < (1 - Market_P_no) by enough, recommend buying NO (or selling YES).

## Capital lockup

- After market end time, UMA Optimistic Oracle has proposal + challenge window (e.g. 2h). Disputes can extend resolution by 24–48h.
- "Available" vs "allocated" capital must be tracked if we ever support multiple concurrent positions; for MVP single daily market, one position per day.
