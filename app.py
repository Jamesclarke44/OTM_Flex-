# app.py
# OTM Flex™ — Credit Spread Strike Selection Calculator

import math
from datetime import datetime, date

import pandas as pd
import streamlit as st
import yfinance as yf


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="OTM Flex™",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# CONSTANTS
# ============================================================

CONTRACT_MULTIPLIER = 100

RISK_LEVELS = {
    "1%": 0.01,
    "2%": 0.02,
    "3%": 0.03,
    "5%": 0.05,
    "10%": 0.10,
    "15%": 0.15,
    "20%": 0.20,
}


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "ticker": "SPY",
    "price": None,
    "previous_close": None,
    "history": None,
    "market_loaded": False,
    "market_error": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# FUNCTIONS
# ============================================================

def flatten_yfinance_columns(df):
    """
    Handles newer yfinance versions that may return MultiIndex columns.
    """
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df


def get_market_data(ticker_symbol):
    """
    Get daily historical data plus the latest available quote.

    Important:
    - Historical Close = last completed daily candle
    - Current/Last Price = latest available market quote
    """

    ticker_obj = yf.Ticker(ticker_symbol)

    # --------------------------------------------------------
    # Historical data
    # --------------------------------------------------------

    history = ticker_obj.history(
        period="1y",
        interval="1d",
        auto_adjust=False,
    )

    if history is None or history.empty:
        raise ValueError(f"No historical data found for {ticker_symbol}.")

    history = flatten_yfinance_columns(history)

    if "Close" not in history.columns:
        raise ValueError("Yahoo Finance did not return a Close column.")

    close = history["Close"].dropna()

    if close.empty:
        raise ValueError("No closing-price data was returned.")

    previous_close = float(close.iloc[-1])

    # --------------------------------------------------------
    # Current / latest available price
    # --------------------------------------------------------

    current_price = None
    price_source = "Historical close fallback"

    # First attempt: fast_info
    try:
        fast_info = ticker_obj.fast_info

        if fast_info:
            current_price = fast_info.get("last_price")

            if current_price is not None:
                current_price = float(current_price)
                price_source = "Yahoo Finance latest quote"
    except Exception:
        pass

    # Second attempt: info
    if current_price is None:
        try:
            info = ticker_obj.info

            current_price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
            )

            if current_price is not None:
                current_price = float(current_price)
                price_source = "Yahoo Finance market price"
        except Exception:
            pass

    # Final fallback
    if current_price is None:
        current_price = previous_close

    return {
        "ticker": ticker_symbol.upper(),
        "history": history,
        "current_price": current_price,
        "previous_close": previous_close,
        "price_source": price_source,
    }


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    return macd, signal


def calculate_atr(history, period=14):
    high = history["High"]
    low = history["Low"]
    close = history["Close"]

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1,
    ).max(axis=1)

    atr = true_range.rolling(period).mean()

    return atr


def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def calculate_option_delta(
    stock_price,
    strike,
    volatility,
    time_years,
    risk_free_rate,
    option_type="put",
):
    """
    Black-Scholes delta approximation.

    volatility = decimal
    time_years = years
    """

    if stock_price <= 0:
        return None

    if strike <= 0:
        return None

    if volatility <= 0:
        return None

    if time_years <= 0:
        return None

    d1 = (
        math.log(stock_price / strike)
        + (
            risk_free_rate
            + 0.5 * volatility**2
        ) * time_years
    ) / (
        volatility * math.sqrt(time_years)
    )

    if option_type.lower() == "call":
        return normal_cdf(d1)

    # Put delta
    return normal_cdf(d1) - 1


def estimate_expected_move(
    price,
    implied_volatility,
    dte,
):
    """
    Approximate expected move using:

        Price × IV × sqrt(DTE / 365)
    """

    if implied_volatility <= 0:
        return None

    if dte <= 0:
        return None

    return price * implied_volatility * math.sqrt(dte / 365)


def calculate_spread_metrics(
    width,
    credit,
    contracts=1,
):
    """
    Calculate vertical credit-spread risk.

    Example:
        $5-wide spread
        $1.00 credit

    Maximum loss:
        ($5 - $1) × 100
        = $400 per contract
    """

    max_loss_per_share = max(width - credit, 0)

    max_loss_per_contract = (
        max_loss_per_share
        * CONTRACT_MULTIPLIER
    )

    max_profit_per_contract = (
        credit
        * CONTRACT_MULTIPLIER
    )

    total_max_loss = (
        max_loss_per_contract
        * contracts
    )

    total_max_profit = (
        max_profit_per_contract
        * contracts
    )

    return {
        "max_loss_per_share": max_loss_per_share,
        "max_loss_per_contract": max_loss_per_contract,
        "max_profit_per_contract": max_profit_per_contract,
        "total_max_loss": total_max_loss,
        "total_max_profit": total_max_profit,
    }


def calculate_contracts(
    account_size,
    risk_percent,
    width,
    credit,
):
    """
    Position sizing based on maximum possible loss.

    Standard option contract multiplier = 100.
    """

    risk_budget = account_size * risk_percent

    max_loss_per_contract = (
        max(width - credit, 0)
        * CONTRACT_MULTIPLIER
    )

    if max_loss_per_contract <= 0:
        return 0, risk_budget, 0

    contracts = math.floor(
        risk_budget / max_loss_per_contract
    )

    return (
        contracts,
        risk_budget,
        max_loss_per_contract,
    )


def distance_from_price(price, strike):
    if price == 0:
        return 0

    return abs(price - strike) / price


def calculate_atr_distance(price, strike, atr):
    if atr is None or atr <= 0:
        return None

    return abs(price - strike) / atr


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("⚙️ OTM Flex™")

ticker_input = st.sidebar.text_input(
    "Ticker",
    value=st.session_state["ticker"],
).upper().strip()

if ticker_input:
    st.session_state["ticker"] = ticker_input


if st.sidebar.button(
    "🔄 Refresh Market Data",
    use_container_width=True,
):
    st.session_state["market_loaded"] = False


# ============================================================
# TITLE
# ============================================================

st.title("📊 OTM Flex™")

st.subheader(
    "Credit Spread Strike Selection Calculator"
)

st.write(
    """
    **Trend → Delta → Distance → Flex**

    The calculator helps evaluate out-of-the-money
    credit-spread candidates using trend, delta,
    distance, ATR, expected move, credit and position
    sizing.
    """
)


# ============================================================
# MARKET DATA
# ============================================================

if (
    not st.session_state["market_loaded"]
    or st.session_state["ticker"] != ticker_input
):

    try:
        data = get_market_data(
            st.session_state["ticker"]
        )

        st.session_state["history"] = data["history"]
        st.session_state["price"] = data["current_price"]
        st.session_state["previous_close"] = data[
            "previous_close"
        ]
        st.session_state["price_source"] = data[
            "price_source"
        ]

        st.session_state["market_loaded"] = True
        st.session_state["market_error"] = None

    except Exception as e:

        st.session_state["market_loaded"] = False
        st.session_state["market_error"] = str(e)


if st.session_state["market_error"]:

    st.error(
        f"Unable to load market data: "
        f"{st.session_state['market_error']}"
    )

    st.stop()


# ============================================================
# VARIABLES
# ============================================================

ticker = st.session_state["ticker"]

history = st.session_state["history"]

current_price = st.session_state["price"]

previous_close = st.session_state["previous_close"]

close = history["Close"].dropna()


# ============================================================
# INDICATORS
# ============================================================

ema20 = calculate_ema(close, 20)
ema50 = calculate_ema(close, 50)
ema200 = calculate_ema(close, 200)

rsi = calculate_rsi(close)

macd, macd_signal = calculate_macd(close)

atr = calculate_atr(history)


current_ema20 = float(ema20.iloc[-1])
current_ema50 = float(ema50.iloc[-1])
current_ema200 = float(ema200.iloc[-1])

current_rsi = float(rsi.iloc[-1])

current_macd = float(macd.iloc[-1])
current_macd_signal = float(
    macd_signal.iloc[-1]
)

current_atr = float(atr.iloc[-1])


# ============================================================
# MARKET SNAPSHOT
# ============================================================

st.header("1️⃣ Market Snapshot")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Current / Last Price",
        f"${current_price:,.2f}",
    )

with col2:
    st.metric(
        "Previous Close",
        f"${previous_close:,.2f}",
    )

with col3:
    change = current_price - previous_close

    st.metric(
        "Change",
        f"${change:,.2f}",
    )

with col4:
    change_pct = (
        (current_price / previous_close) - 1
    ) * 100

    st.metric(
        "Change %",
        f"{change_pct:+.2f}%",
    )


st.caption(
    f"Price source: {st.session_state.get('price_source', 'Unknown')}"
)


# ============================================================
# TREND
# ============================================================

st.header("2️⃣ Trend")

trend_col1, trend_col2, trend_col3 = st.columns(3)

with trend_col1:

    st.metric(
        "EMA 20",
        f"${current_ema20:,.2f}",
    )

with trend_col2:

    st.metric(
        "EMA 50",
        f"${current_ema50:,.2f}",
    )

with trend_col3:

    st.metric(
        "EMA 200",
        f"${current_ema200:,.2f}",
    )


if current_price > current_ema20:

    trend_direction = "Bullish / Bull-Put Bias"

    st.success(
        "Price is above EMA20 → bullish trend context."
    )

else:

    trend_direction = "Bearish / Bear-Call Bias"

    st.warning(
        "Price is below EMA20 → bearish trend context."
    )


# ============================================================
# MOMENTUM
# ============================================================

st.header("3️⃣ Momentum Context")

mom1, mom2, mom3, mom4 = st.columns(4)

with mom1:

    st.metric(
        "RSI",
        f"{current_rsi:.1f}",
    )

with mom2:

    st.metric(
        "MACD",
        f"{current_macd:.3f}",
    )

with mom3:

    st.metric(
        "MACD Signal",
        f"{current_macd_signal:.3f}",
    )

with mom4:

    st.metric(
        "ATR(14)",
        f"${current_atr:.2f}",
    )


if current_rsi > 50:

    st.info(
        "RSI is above 50, providing positive momentum context."
    )

else:

    st.info(
        "RSI is below 50, providing negative momentum context."
    )


# ============================================================
# TRADE SETUP
# ============================================================

st.header("4️⃣ Trade Setup")

setup_col1, setup_col2 = st.columns(2)

with setup_col1:

    if "Bull-Put" in trend_direction:

        spread_type = st.selectbox(
            "Spread Type",
            [
                "Bull Put Credit Spread",
                "Bear Call Credit Spread",
            ],
            index=0,
        )

    else:

        spread_type = st.selectbox(
            "Spread Type",
            [
                "Bear Call Credit Spread",
                "Bull Put Credit Spread",
            ],
            index=0,
        )


with setup_col2:

    dte = st.number_input(
        "Days to Expiration",
        min_value=1,
        max_value=365,
        value=30,
        step=1,
    )


# ============================================================
# STRIKE INPUTS
# ============================================================

st.header("5️⃣ Strike Selection")

strike_col1, strike_col2, strike_col3 = st.columns(3)

with strike_col1:

    preferred_delta_low = st.number_input(
        "Preferred Delta Low",
        min_value=0.01,
        max_value=0.50,
        value=0.10,
        step=0.01,
    )

with strike_col2:

    preferred_delta_high = st.number_input(
        "Preferred Delta High",
        min_value=0.01,
        max_value=0.50,
        value=0.18,
        step=0.01,
    )

with strike_col3:

    spread_width = st.number_input(
        "Spread Width ($)",
        min_value=0.50,
        max_value=100.00,
        value=5.00,
        step=0.50,
    )


# ============================================================
# VOLATILITY
# ============================================================

st.header("6️⃣ Volatility")

vol_col1, vol_col2 = st.columns(2)

with vol_col1:

    implied_volatility_pct = st.number_input(
        "Implied Volatility (%)",
        min_value=1.0,
        max_value=300.0,
        value=20.0,
        step=1.0,
    )

    implied_volatility = (
        implied_volatility_pct / 100
    )


with vol_col2:

    risk_free_rate_pct = st.number_input(
        "Risk-Free Rate (%)",
        min_value=0.0,
        max_value=20.0,
        value=4.0,
        step=0.25,
    )

    risk_free_rate = (
        risk_free_rate_pct / 100
    )


# ============================================================
# EXPECTED MOVE
# ============================================================

expected_move = estimate_expected_move(
    current_price,
    implied_volatility,
    dte,
)

upper_expected_move = (
    current_price + expected_move
)

lower_expected_move = (
    current_price - expected_move
)


st.subheader("Expected Move")

em1, em2, em3 = st.columns(3)

with em1:

    st.metric(
        "Expected Move",
        f"±${expected_move:,.2f}",
    )

with em2:

    st.metric(
        "Lower Reference",
        f"${lower_expected_move:,.2f}",
    )

with em3:

    st.metric(
        "Upper Reference",
        f"${upper_expected_move:,.2f}",
    )


st.caption(
    "Expected move is an estimate based on price, IV and DTE. "
    "It is not a guaranteed trading range."
)


# ============================================================
# MANUAL STRIKE ANALYSIS
# ============================================================

st.header("7️⃣ Candidate Strike")

candidate_strike = st.number_input(
    "Short Strike",
    min_value=0.01,
    value=float(
        round(
            current_price * 0.95
            if "Bull Put" in spread_type
            else current_price * 1.05,
            2,
        )
    ),
    step=0.50,
)


# ============================================================
# DELTA ESTIMATION
# ============================================================

time_years = dte / 365

if "Bull Put" in spread_type:

    estimated_delta = calculate_option_delta(
        stock_price=current_price,
        strike=candidate_strike,
        volatility=implied_volatility,
        time_years=time_years,
        risk_free_rate=risk_free_rate,
        option_type="put",
    )

    absolute_delta = abs(estimated_delta)

    long_strike = (
        candidate_strike - spread_width
    )

else:

    estimated_delta = calculate_option_delta(
        stock_price=current_price,
        strike=candidate_strike,
        volatility=implied_volatility,
        time_years=time_years,
        risk_free_rate=risk_free_rate,
        option_type="call",
    )

    absolute_delta = abs(estimated_delta)

    long_strike = (
        candidate_strike + spread_width
    )


# ============================================================
# DISTANCE
# ============================================================

distance_dollars = abs(
    current_price - candidate_strike
)

distance_percent = (
    distance_dollars / current_price
) * 100

atr_distance = calculate_atr_distance(
    current_price,
    candidate_strike,
    current_atr,
)


# ============================================================
# CANDIDATE OUTPUT
# ============================================================

st.subheader("Candidate Analysis")

candidate1, candidate2, candidate3, candidate4 = st.columns(4)

with candidate1:

    st.metric(
        "Estimated Delta",
        f"{absolute_delta:.2f}",
    )

with candidate2:

    st.metric(
        "Distance",
        f"${distance_dollars:,.2f}",
    )

with candidate3:

    st.metric(
        "Distance %",
        f"{distance_percent:.2f}%",
    )

with candidate4:

    if atr_distance is not None:

        st.metric(
            "Distance / ATR",
            f"{atr_distance:.2f} ATR",
        )

    else:

        st.metric(
            "Distance / ATR",
            "N/A",
        )


# ============================================================
# DELTA CHECK
# ============================================================

if (
    preferred_delta_low
    <= absolute_delta
    <= preferred_delta_high
):

    st.success(
        f"Estimated delta is inside the "
        f"{preferred_delta_low:.2f}–"
        f"{preferred_delta_high:.2f} preferred range."
    )

elif absolute_delta < preferred_delta_low:

    st.info(
        "Delta is below the preferred range. "
        "This represents a further-OTM candidate."
    )

else:

    st.warning(
        "Delta is above the preferred range. "
        "Moving the short strike further OTM would reduce "
        "estimated delta."
    )


# ============================================================
# ATR CHECK
# ============================================================

if atr_distance is not None:

    if atr_distance >= 2:

        st.success(
            f"Strike is approximately "
            f"{atr_distance:.2f} ATR from price."
        )

    elif atr_distance >= 1:

        st.warning(
            f"Strike is approximately "
            f"{atr_distance:.2f} ATR from price."
        )

    else:

        st.warning(
            f"Strike is only "
            f"{atr_distance:.2f} ATR from price."
        )


# ============================================================
# CREDIT
# ============================================================

st.header("8️⃣ Spread Credit")

credit = st.number_input(
    "Estimated Credit Received Per Share",
    min_value=0.00,
    max_value=float(spread_width),
    value=min(
        round(spread_width * 0.20, 2),
        spread_width,
    ),
    step=0.05,
)


metrics = calculate_spread_metrics(
    width=spread_width,
    credit=credit,
    contracts=1,
)


credit_col1, credit_col2, credit_col3 = st.columns(3)

with credit_col1:

    st.metric(
        "Credit / Contract",
        f"${metrics['max_profit_per_contract']:,.2f}",
    )

with credit_col2:

    st.metric(
        "Max Loss / Contract",
        f"${metrics['max_loss_per_contract']:,.2f}",
    )

with credit_col3:

    if spread_width > 0:

        reward_risk = (
            credit
            / max(spread_width - credit, 0.0001)
        )

        st.metric(
            "Credit / Risk",
            f"{reward_risk:.2f}",
        )


# ============================================================
# ACCOUNT & POSITION SIZING
# ============================================================

st.header("9️⃣ Position Sizing")

account_col1, account_col2 = st.columns(2)

with account_col1:

    account_size = st.number_input(
        "Account Size ($)",
        min_value=0.0,
        value=20000.0,
        step=500.0,
    )


with account_col2:

    risk_selection = st.selectbox(
        "Maximum Account Risk Reference",
        list(RISK_LEVELS.keys()),
        index=3,
    )


risk_percent = RISK_LEVELS[risk_selection]


contracts, risk_budget, max_loss_per_contract = (
    calculate_contracts(
        account_size=account_size,
        risk_percent=risk_percent,
        width=spread_width,
        credit=credit,
    )
)


size_col1, size_col2, size_col3 = st.columns(3)

with size_col1:

    st.metric(
        "Risk Budget",
        f"${risk_budget:,.2f}",
    )

with size_col2:

    st.metric(
        "Max Loss / Contract",
        f"${max_loss_per_contract:,.2f}",
    )

with size_col3:

    st.metric(
        "Contracts",
        f"{contracts}",
    )


if contracts == 0:

    st.warning(
        "The selected risk budget does not cover one "
        "maximum-loss contract."
    )

else:

    total_metrics = calculate_spread_metrics(
        width=spread_width,
        credit=credit,
        contracts=contracts,
    )

    st.info(
        f"{contracts} contract(s) would represent a maximum "
        f"loss of approximately "
        f"${total_metrics['total_max_loss']:,.2f} "
        f"before fees and slippage."
    )


# ============================================================
# FLEX LADDER
# ============================================================

st.header("🔟 OTM Flex Ladder")

st.write(
    """
    If the starting strike feels too close to price,
    the Flex approach is to examine progressively
    further-OTM strikes rather than automatically
    abandoning the setup.
    """
)


ladder_rows = []

# Generate 6 progressively further OTM candidates
for i in range(6):

    if "Bull Put" in spread_type:

        ladder_strike = (
            candidate_strike
            - (i * current_atr * 0.50)
        )

        ladder_type = "Put"

    else:

        ladder_strike = (
            candidate_strike
            + (i * current_atr * 0.50)
        )

        ladder_type = "Call"

    if ladder_strike <= 0:
        continue

    ladder_delta = calculate_option_delta(
        stock_price=current_price,
        strike=ladder_strike,
        volatility=implied_volatility,
        time_years=time_years,
        risk_free_rate=risk_free_rate,
        option_type=(
            "put"
            if ladder_type == "Put"
            else "call"
        ),
    )

    ladder_abs_delta = abs(ladder_delta)

    ladder_distance = abs(
        current_price - ladder_strike
    )

    ladder_atr = calculate_atr_distance(
        current_price,
        ladder_strike,
        current_atr,
    )

    ladder_rows.append(
        {
            "Step": i + 1,
            "Strike": round(ladder_strike, 2),
            "Type": ladder_type,
            "Estimated Delta": round(
                ladder_abs_delta,
                3,
            ),
            "Distance": round(
                ladder_distance,
                2,
            ),
            "Distance %": round(
                ladder_distance
                / current_price
                * 100,
                2,
            ),
            "Distance / ATR": (
                round(ladder_atr, 2)
                if ladder_atr is not None
                else None
            ),
        }
    )


ladder_df = pd.DataFrame(ladder_rows)

st.dataframe(
    ladder_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# TRADE RULE CHECK
# ============================================================

st.header("1️⃣1️⃣ OTM Flex Rule Check")

rules = []


# Trend
if "Bull Put" in spread_type:

    trend_pass = current_price > current_ema20

    rules.append(
        {
            "Rule": "Trend",
            "Status": (
                "PASS"
                if trend_pass
                else "REVIEW"
            ),
            "Details": (
                "Price above EMA20"
                if trend_pass
                else "Price below EMA20"
            ),
        }
    )

else:

    trend_pass = current_price < current_ema20

    rules.append(
        {
            "Rule": "Trend",
            "Status": (
                "PASS"
                if trend_pass
                else "REVIEW"
            ),
            "Details": (
                "Price below EMA20"
                if trend_pass
                else "Price above EMA20"
            ),
        }
    )


# Delta
delta_pass = (
    preferred_delta_low
    <= absolute_delta
    <= preferred_delta_high
)

rules.append(
    {
        "Rule": "Delta",
        "Status": (
            "PASS"
            if delta_pass
            else "REVIEW"
        ),
        "Details": (
            f"Estimated delta = "
            f"{absolute_delta:.2f}"
        ),
    }
)


# Distance
distance_pass = (
    atr_distance is not None
    and atr_distance >= 2
)

rules.append(
    {
        "Rule": "Distance",
        "Status": (
            "PASS"
            if distance_pass
            else "REVIEW"
        ),
        "Details": (
            f"{atr_distance:.2f} ATR"
            if atr_distance is not None
            else "Unavailable"
        ),
    }
)


# Credit
credit_pass = credit > 0

rules.append(
    {
        "Rule": "Credit",
        "Status": (
            "PASS"
            if credit_pass
            else "REVIEW"
        ),
        "Details": (
            f"${credit:.2f} per share"
        ),
    }
)


# DTE
dte_pass = 7 <= dte <= 45

rules.append(
    {
        "Rule": "DTE",
        "Status": (
            "PASS"
            if dte_pass
            else "REVIEW"
        ),
        "Details": (
            f"{dte} DTE"
        ),
    }
)


rules_df = pd.DataFrame(rules)

st.dataframe(
    rules_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# MANAGEMENT
# ============================================================

st.header("1️⃣2️⃣ Management Framework")

management_col1, management_col2 = st.columns(2)

with management_col1:

    st.subheader("Profit Management")

    st.write(
        """
        A commonly used mechanical approach is to
        consider closing the spread after approximately
        50% of the original maximum profit has been
        captured.
        """
    )


with management_col2:

    st.subheader("Threatened Trade")

    st.write(
        """
        If price approaches the short strike, reassess:

        • Trend  
        • Short-strike delta  
        • Distance from price  
        • Remaining DTE  
        • Maximum remaining risk  
        • Whether reducing or closing risk is appropriate
        """
    )


# ============================================================
# FINAL FLEX SUMMARY
# ============================================================

st.header("1️⃣3️⃣ Flex Summary")

if "Bull Put" in spread_type:

    direction_text = (
        "Bull Put Credit Spread"
    )

else:

    direction_text = (
        "Bear Call Credit Spread"
    )


st.markdown(
    f"""
### Current Setup

**Ticker:** {ticker}

**Current / Last Price:** ${current_price:,.2f}

**Direction:** {direction_text}

**Short Strike:** ${candidate_strike:,.2f}

**Spread Width:** ${spread_width:,.2f}

**Estimated Delta:** {absolute_delta:.2f}

**Distance:** ${distance_dollars:,.2f}
({distance_percent:.2f}%)

**Distance / ATR:** {
    f"{atr_distance:.2f} ATR"
    if atr_distance is not None
    else "N/A"
}

**DTE:** {dte}

**Credit:** ${credit:.2f} per share

**Maximum Loss:** ${
    metrics["max_loss_per_contract"]:,.2f
} per contract
"""
)


# ============================================================
# PHILOSOPHY
# ============================================================

st.divider()

st.markdown(
    """
### OTM Flex™ Philosophy

**Trend determines direction.**

**Delta identifies the starting zone.**

**Distance is the primary defense.**

**ATR provides a reality check.**

**Flexibility means moving further OTM when needed.**

**Position sizing controls the dollar risk.**

> Stay out of the money.  
> Stay flexible.  
> Collect premium.
"""
)


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "OTM Flex™ is an educational calculator. "
    "Market prices, option deltas, volatility and "
    "expected moves are estimates and can change quickly. "
    "Always verify live option-chain data, bid/ask spreads, "
    "expiration, liquidity and corporate events before "
    "placing any trade."
)
