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
st.caption("Trend → Delta → Distance → Flex. Manual data entry (live data source pluggable later).")

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

col1, col2 = st.columns(2)
with col1:
    price = st.number_input("Current price", min_value=0.01, value=100.00, step=0.01, format="%.2f")
with col2:
    ema20 = st.number_input("EMA20", min_value=0.01, value=98.00, step=0.01, format="%.2f")

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

trend_strength = st.radio(
    "Trend strength (your read on chart/context)",
    options=["Strong", "Average", "Choppy / uncertain"],
    index=1,
    horizontal=True,
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
