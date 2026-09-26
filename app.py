import streamlit as st

st.set_page_config(
    page_title="OTM Flex",
    page_icon="📈",
    layout="wide"
)

# ------------------
# HEADER
# ------------------

st.title("📈 OTM Flex")
st.subheader("Stay Out of the Money. Stay Flexible. Collect Premium.")

# ------------------
# INPUTS
# ------------------

st.sidebar.header("Trade Inputs")

ticker = st.sidebar.text_input(
    "Ticker",
    value="QQQ"
)

price = st.sidebar.number_input(
    "Current Price",
    value=745.00
)

ema20 = st.sidebar.number_input(
    "EMA20",
    value=725.00
)

atr = st.sidebar.number_input(
    "ATR",
    value=10.00
)

delta = st.sidebar.number_input(
    "Short Strike Delta",
    value=0.15,
    step=0.01
)

credit = st.sidebar.number_input(
    "Credit Received",
    value=0.50,
    step=0.01
)

distance = st.sidebar.number_input(
    "Distance From Price",
    value=20.00
)

# ------------------
# DETERMINE TRADE
# ------------------

if price > ema20:
    trade_type = "Bull Put Spread"
    trend_score = 40
else:
    trade_type = "Bear Call Spread"
    trend_score = 40

# ------------------
# DELTA SCORE
# ------------------

if 0.10 <= abs(delta) <= 0.18:
    delta_score = 30
else:
    delta_score = 10

# ------------------
# CREDIT SCORE
# ------------------

if credit >= 0.50:
    credit_score = 20
else:
    credit_score = 5

# ------------------
# DISTANCE SCORE
# ------------------

atr_multiple = distance / atr

if atr_multiple >= 1.5:
    distance_score = 10
else:
    distance_score = 5

# ------------------
# TOTAL SCORE
# ------------------

score = (
    trend_score
    + delta_score
    + credit_score
    + distance_score
)

# ------------------
# STATUS
# ------------------

if score >= 90:
    status = "✅ Excellent"
elif score >= 80:
    status = "✅ Good"
elif score >= 70:
    status = "⚠️ Acceptable"
else:
    status = "❌ Pass"

# ------------------
# DISPLAY
# ------------------

col1, col2 = st.columns(2)

with col1:

    st.metric("Ticker", ticker)

    st.metric(
        "Strategy",
        trade_type
    )

    st.metric(
        "OTM Flex Score",
        score
    )

    st.metric(
        "Status",
        status
    )

with col2:

    st.metric(
        "ATR Multiple",
        round(atr_multiple, 2)
    )

    st.metric(
        "Delta",
        delta
    )

    st.metric(
        "Credit",
        f"${credit:.2f}"
    )

st.divider()

st.markdown("## OTM Flex Analysis")

if atr_multiple < 1.5:
    st.warning(
        "Strike may be too close. Consider moving further OTM."
    )

if abs(delta) > 0.18:
    st.warning(
        "Delta too high. Consider moving further OTM."
    )

if credit < 0.50:
    st.warning(
        "Credit below preferred minimum."
    )

st.success(
    "When in doubt, go further OTM."
)
