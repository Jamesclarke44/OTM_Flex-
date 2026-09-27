"""
OTM Flex - Credit Spread Strike Selection Calculator

A manual-entry Streamlit tool that implements the OTM Flex rule book:
trend -> delta -> distance -> flex.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="OTM Flex Calculator", page_icon="📉", layout="centered")

st.title("📉 OTM Flex — Strike Selection Calculator")
st.caption("Trend → Delta → Distance → Flex. Manual data entry; trend strength is scored automatically from EMA20/50/200, RSI, and MACD.")

with st.expander("Rule book summary", expanded=False):
    st.markdown(
        """
- **Trend:** price above EMA20 → Bull Put Spread. Price below EMA20 → Bear Call Spread.
- **Delta:** target short strike delta **0.10–0.18**.
- **Distance:** use ATR as a reality check — stronger trend allows closer strikes (1–2 ATR),
  choppy/uncertain conditions call for more distance (2–3 ATR).
- **Flex:** if a candidate strike feels too risky, move further OTM rather than skipping the trade.
- **Expiration:** typically 7–45 DTE.
- **Profit target:** close near 50% of max profit.
- **Golden rule:** choose the closest strike that still lets you sleep well at night.
        """
    )

# ---------------------------------------------------------------------------
# 1. Trend
# ---------------------------------------------------------------------------
st.header("1. Trend")

col1, col2, col3 = st.columns(3)
with col1:
    price = st.number_input("Current price", min_value=0.01, value=100.00, step=0.01, format="%.2f")
with col2:
    ema20 = st.number_input("EMA20", min_value=0.01, value=98.00, step=0.01, format="%.2f")
with col3:
    ema50 = st.number_input("EMA50", min_value=0.01, value=96.00, step=0.01, format="%.2f")

ema200 = st.number_input("EMA200", min_value=0.01, value=90.00, step=0.01, format="%.2f")

if price > ema20:
    direction = "Bull Put Spread"
    side = "put"
    st.success(f"Price is above EMA20 → **{direction}**")
elif price < ema20:
    direction = "Bear Call Spread"
    side = "call"
    st.error(f"Price is below EMA20 → **{direction}**")
else:
    direction = None
    side = None
    st.warning("Price equals EMA20 — no clear trend signal. Consider waiting or checking a longer timeframe.")

# ---------------------------------------------------------------------------
# 1b. Momentum inputs (feed the auto trend-strength score)
# ---------------------------------------------------------------------------
st.subheader("Momentum (for automatic trend strength)")
col4, col5, col6 = st.columns(3)
with col4:
    rsi = st.number_input("RSI (14)", min_value=0.0, max_value=100.0, value=55.0, step=0.5)
with col5:
    macd_line = st.number_input("MACD line", value=0.30, step=0.01, format="%.2f")
with col6:
    macd_signal = st.number_input("MACD signal", value=0.15, step=0.01, format="%.2f")

macd_hist = macd_line - macd_signal


def score_ema_stack(side, ema20, ema50, ema200):
    if side == "put":  # bullish stack expected
        if ema20 > ema50 > ema200:
            return 2, "Full bullish stack (EMA20 > EMA50 > EMA200)"
        elif ema20 > ema50:
            return 1, "Partial bullish stack (EMA20 > EMA50, but EMA50 ≤ EMA200)"
        else:
            return 0, "No bullish stack"
    elif side == "call":  # bearish stack expected
        if ema20 < ema50 < ema200:
            return 2, "Full bearish stack (EMA20 < EMA50 < EMA200)"
        elif ema20 < ema50:
            return 1, "Partial bearish stack (EMA20 < EMA50, but EMA50 ≥ EMA200)"
        else:
            return 0, "No bearish stack"
    return 0, "No trend direction"


def score_rsi(side, rsi):
    if side == "put":
        if 50 <= rsi <= 70:
            return 2, "RSI in healthy uptrend zone (50–70)"
        elif 40 <= rsi < 50 or 70 < rsi <= 80:
            return 1, "RSI borderline (40–50 or 70–80)"
        else:
            return 0, "RSI too weak (<40) or overextended (>80)"
    elif side == "call":
        if 30 <= rsi <= 50:
            return 2, "RSI in healthy downtrend zone (30–50)"
        elif 20 <= rsi < 30 or 50 < rsi <= 60:
            return 1, "RSI borderline (20–30 or 50–60)"
        else:
            return 0, "RSI too weak (>60) or overextended (<20)"
    return 0, "No trend direction"


def score_macd(side, macd_line, macd_signal, macd_hist):
    if side == "put":
        if macd_line > macd_signal and macd_hist > 0:
            return 2, "MACD above signal, rising histogram"
        elif macd_line > macd_signal:
            return 1, "MACD above signal, but histogram flat/falling"
        else:
            return 0, "MACD below signal"
    elif side == "call":
        if macd_line < macd_signal and macd_hist < 0:
            return 2, "MACD below signal, falling histogram"
        elif macd_line < macd_signal:
            return 1, "MACD below signal, but histogram flat/rising"
        else:
            return 0, "MACD above signal"
    return 0, "No trend direction"


ema_pts, ema_note = score_ema_stack(side, ema20, ema50, ema200)
rsi_pts, rsi_note = score_rsi(side, rsi)
macd_pts, macd_note = score_macd(side, macd_line, macd_signal, macd_hist)
total_score = ema_pts + rsi_pts + macd_pts

if total_score >= 5:
    trend_strength = "Strong"
elif total_score >= 3:
    trend_strength = "Average"
else:
    trend_strength = "Choppy / uncertain"

st.markdown(f"**Auto trend strength: {trend_strength}** (score {total_score}/6)")
with st.expander("Trend strength breakdown", expanded=False):
    st.dataframe(
        pd.DataFrame(
            [
                {"Factor": "EMA stack", "Points": f"{ema_pts}/2", "Detail": ema_note},
                {"Factor": "RSI", "Points": f"{rsi_pts}/2", "Detail": rsi_note},
                {"Factor": "MACD", "Points": f"{macd_pts}/2", "Detail": macd_note},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# 2. Distance (ATR reality check)
# ---------------------------------------------------------------------------
st.header("2. Distance — ATR Reality Check")

atr = st.number_input("ATR (e.g. 14-day)", min_value=0.01, value=2.50, step=0.01, format="%.2f")

atr_guidance = {
    "Strong": (1.0, 2.0),
    "Average": (2.0, 2.0),
    "Choppy / uncertain": (2.0, 3.0),
}
low_mult, high_mult = atr_guidance[trend_strength]

st.write(f"Guideline for **{trend_strength}** trend: **{low_mult}–{high_mult} ATR** away from price.")

atr_rows = []
for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
    distance = atr * mult
    if side == "put":
        strike = price - distance
    elif side == "call":
        strike = price + distance
    else:
        strike = None
    in_range = low_mult <= mult <= high_mult
    atr_rows.append(
        {
            "ATR multiple": f"{mult}x",
            "Distance ($)": round(distance, 2),
            "Implied strike": round(strike, 2) if strike is not None else "—",
            "Within guideline": "✅" if in_range else "",
        }
    )

st.dataframe(pd.DataFrame(atr_rows), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# 3. Delta cross-check
# ---------------------------------------------------------------------------
st.header("3. Delta Cross-Check")
st.caption("Enter candidate strikes and their short-strike delta (from your broker's chain) to find the sweet spot.")

default_rows = pd.DataFrame(
    {
        "Strike": [round(price - atr * m, 2) if side == "put" else round(price + atr * m, 2) for m in [1.0, 1.5, 2.0, 2.5, 3.0]],
        "Delta": [0.22, 0.18, 0.14, 0.11, 0.08],
    }
)

edited = st.data_editor(
    default_rows,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Delta": st.column_config.NumberColumn(format="%.2f", min_value=0.0, max_value=1.0, step=0.01),
    },
)

def evaluate_row(row):
    delta_ok = 0.10 <= row["Delta"] <= 0.18
    if side == "put":
        distance = price - row["Strike"]
    elif side == "call":
        distance = row["Strike"] - price
    else:
        distance = None
    atr_mult = distance / atr if (distance is not None and atr) else None
    distance_ok = (atr_mult is not None) and (low_mult <= atr_mult <= high_mult)
    return pd.Series(
        {
            "Distance ($)": round(distance, 2) if distance is not None else None,
            "ATR multiple": round(atr_mult, 2) if atr_mult is not None else None,
            "Delta in 0.10–0.18": "✅" if delta_ok else "",
            "Distance in guideline": "✅" if distance_ok else "",
            "Both ✅": "⭐" if (delta_ok and distance_ok) else "",
        }
    )

if side is not None and not edited.empty:
    results = pd.concat([edited, edited.apply(evaluate_row, axis=1)], axis=1)
    st.dataframe(results, hide_index=True, use_container_width=True)

    starred = results[results["Both ✅"] == "⭐"]
    if not starred.empty:
        # Closest to price among the qualifying strikes = OTM Flex "golden rule" pick
        if side == "put":
            best = starred.loc[starred["Strike"].idxmax()]
        else:
            best = starred.loc[starred["Strike"].idxmin()]
        st.info(
            f"**Suggested strike (golden rule — closest qualifying strike): {best['Strike']}** "
            f"(delta {best['Delta']:.2f}, {best['ATR multiple']} ATR away)"
        )
    else:
        st.warning(
            "No candidate strike is in both the delta band and the ATR guideline. "
            "Per the Flex Rule, move further OTM and re-check — don't reject the trade outright."
        )

# ---------------------------------------------------------------------------
# 4. Expiration
# ---------------------------------------------------------------------------
st.header("4. Expiration")
dte = st.slider("Days to expiration (DTE)", min_value=1, max_value=60, value=21)
if 7 <= dte <= 45:
    st.success(f"{dte} DTE is within the typical 7–45 DTE range.")
else:
    st.warning(f"{dte} DTE is outside the typical 7–45 DTE range — proceed deliberately.")

# ---------------------------------------------------------------------------
# 5. Credit & profit target
# ---------------------------------------------------------------------------
st.header("5. Credit & Profit Target")
col3, col4 = st.columns(2)
with col3:
    credit = st.number_input("Credit received ($ per spread)", min_value=0.0, value=1.00, step=0.01, format="%.2f")
with col4:
    width = st.number_input("Spread width ($)", min_value=0.01, value=5.00, step=0.5, format="%.2f")

max_loss = max(width - credit, 0)
profit_target = credit * 0.5
roc = (credit / max_loss * 100) if max_loss else None

m1, m2, m3 = st.columns(3)
m1.metric("Max loss / spread", f"${max_loss:.2f}")
m2.metric("50% profit target (buy back at)", f"${profit_target:.2f}")
m3.metric("Return on capital at risk", f"{roc:.1f}%" if roc is not None else "—")

# ---------------------------------------------------------------------------
# 6. Position sizing
# ---------------------------------------------------------------------------
st.header("6. Position Sizing")
account_size = st.number_input("Account size ($)", min_value=0.0, value=25000.0, step=500.0)
risk_pct = st.slider("Max risk per trade (% of account)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)

max_risk_dollars = account_size * (risk_pct / 100)
max_contracts = int(max_risk_dollars // max_loss) if max_loss else 0

st.write(f"Max $ risk at {risk_pct}% of account: **${max_risk_dollars:,.2f}**")
st.write(f"Max contracts at this width/credit: **{max_contracts}**")
if max_contracts <= 0:
    st.warning("Spread's max loss exceeds your risk budget at this size — widen strikes, reduce width, or increase account risk %.")

st.divider()
st.caption("Stay out of the money. Stay flexible. Collect premium.")
