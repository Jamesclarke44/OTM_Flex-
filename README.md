# OTM Flex Calculator

A Streamlit tool that implements the OTM Flex credit-spread rule book:
**Trend → Delta → Distance → Flex.**

Manual data entry for now (price, EMA20, ATR, deltas) — designed so a live
data source (yfinance, IBKR, etc.) can be dropped in later without changing
the calculator logic.

## What it does

1. **Trend** — compares price to EMA20 to pick Bull Put Spread vs Bear Call Spread.
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
