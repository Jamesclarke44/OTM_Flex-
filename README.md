# OTM Flex Calculator

A Streamlit tool that implements the OTM Flex credit-spread rule book:
**Trend → Delta → Distance → Flex.**

Manual data entry for now (price, EMA20, ATR, deltas) — designed so a live
data source (yfinance, IBKR, etc.) can be dropped in later without changing
the calculator logic.

## What it does

1. **Trend** — compares price to EMA20 to pick Bull Put Spread vs Bear Call Spread, then
   scores trend **strength automatically** (Strong / Average / Choppy) from three factors
   you enter off your chart, each worth 0–2 points (6 max):
   - EMA stack alignment (EMA20 vs EMA50 vs EMA200)
   - RSI zone (healthy trend range vs weak/overextended)
   - MACD line vs signal line and histogram direction
   Score 5–6 → Strong, 3–4 → Average, 0–2 → Choppy. The breakdown is shown in an expander
   so you can see exactly why it landed where it did.
2. **Distance** — computes 1x–3x ATR strikes and flags which multiples fit your
   stated trend strength (strong/average/choppy).
3. **Delta cross-check** — an editable table where you enter candidate strikes
   and their deltas; it flags which ones hit both the 0.10–0.18 delta band
   *and* the ATR distance guideline, and suggests the closest qualifying
   strike (the "golden rule" pick).
4. **Expiration** — flags whether your chosen DTE is inside the typical 7–45
   DTE window.
5. **Credit & profit target** — max loss, 50%-of-credit profit target, and
   return on capital at risk.
6. **Position sizing** — max contracts given your account size and risk %
   per trade.

## Auto-fetch (free, via Yahoo Finance)

Section 0 lets you type a ticker and pull real data for free (delayed ~15–20
min, no account or API key needed):

- **Price, EMA20/50/200, RSI, MACD, ATR** — computed from Yahoo Finance
  daily bars (`yfinance`). Pre-fills the Trend and Distance sections; every
  value stays editable afterward.
- **Delta estimate** — Section 3 can load a ticker's expirations and pull
  its option chain. Yahoo doesn't publish delta directly, so the app
  computes it itself with **Black-Scholes**, using Yahoo's implied
  volatility as the input. This is a close approximation to your broker's
  real-time delta for liquid names, but it's delayed and won't match
  exactly — treat it as a free starting point, not a replacement for your
  broker's live Greeks.

If a fetch fails (bad ticker, no expirations, rate limiting), the app shows
the error and leaves existing values untouched — nothing crashes, you just
fall back to typing numbers in by hand.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Push to GitHub

```bash
git init
git add .
git commit -m "Initial OTM Flex calculator"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## Next steps (when you're ready to wire up live data)

- Swap the manual `price` / `ema20` / `atr` inputs for a `yfinance` (or IBKR)
  fetch, keeping the rest of the calculation logic untouched.
- Replace the manual delta table with a live option-chain pull, filtered to
  strikes near the ATR-implied range before you even look at delta.
- The core functions (`evaluate_row`, the ATR table logic) are pure and
  don't touch Streamlit state, so they can be lifted into a separate
  `logic.py` module and unit-tested once the app grows.
