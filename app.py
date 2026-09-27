"""
OTM Flex™ — Credit Spread Strike Selection Engine

PHILOSOPHY
----------
Trend → Delta → Distance → Flex

The engine is designed to HELP select a credit spread.
It does not attempt to predict the market.

Core OTM Flex rules:
    1. Price above EMA20 → Bull Put Spread
    2. Price below EMA20 → Bear Call Spread
    3. Target short strike delta = 0.10–0.18
    4. Distance is the primary defence
    5. ATR is a reality check
    6. If uncomfortable → move further OTM
    7. Typical DTE = 7–45
    8. Take profit around 50%
    9. Avoid holding stock spreads through earnings
   10. Require acceptable credit
   11. Size positions conservatively
   12. Stay flexible

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import date, datetime, timedelta
import math

import pandas as pd
import streamlit as st
import yfinance as yf


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OTM Flex™ Credit Spread Engine",
    page_icon="📉",
    layout="centered",
)

st.title("📉 OTM Flex™")
st.subheader("Credit Spread Strike Selection Engine")

st.caption(
    "Trend → Delta → Distance → Flex"
)


# ============================================================
# RULE BOOK
# ============================================================

with st.expander("📖 OTM Flex™ Rule Book", expanded=False):

    st.markdown(
        """
### 1. Trend Rule

**Bull Put Spread**
- Price above EMA20
- Preferably trending higher

**Bear Call Spread**
- Price below EMA20
- Preferably trending lower

---

### 2. Strike Selection

Target short strike delta:

**0.10–0.18**

This is the preferred OTM Flex starting zone.

---

### 3. Flex Rule

If the trade feels too risky:

**Move further OTM.**

Do not automatically reject the trade because of:
- elevated volatility
- weaker trend
- support/resistance
- uncertainty

Instead, move the short strike further OTM.

---

### 4. Risk Management

Distance is the primary defence.

Use:
- Lower delta
- More distance
- Wider margin of safety

---

### 5. Expiration

Typical:

**7–45 DTE**

---

### 6. Profit Taking

Close around:

**50% of maximum profit**

---

### 7. Losing Trade

If threatened:

1. Re-evaluate trend
2. Re-check short-strike delta
3. Re-check distance
4. Consider reducing risk
5. Consider rolling if risk remains manageable

---

### 8. Position Sizing

One spread should be uncomfortable if it loses,
but never catastrophic to the account.

---

### 9. Golden Rule

**Choose the closest strike that still lets you sleep well at night.**

---

### OTM Flex Motto

**Stay out of the money. Stay flexible. Collect premium.**

**When in doubt, go further OTM — not out of the trade.**
"""
    )


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "price": 100.00,
    "ema20": 98.00,
    "ema50": 96.00,
    "ema200": 90.00,
    "rsi": 55.0,
    "macd_line": 0.30,
    "macd_signal": 0.15,
    "atr": 2.50,
    "next_earnings_date": None,
    "data_fetched_at": None,
    "expirations": [],
    "chain_df": None,
    "atm_iv": 20.0,
    "atm_iv_dte": None,
    "chain_version": 0,
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# MATH
# ============================================================

def norm_cdf(x):
    """Standard normal cumulative distribution."""
    return 0.5 * (
        1 + math.erf(x / math.sqrt(2))
    )


def bs_delta(
    spot,
    strike,
    years,
    risk_free,
    iv,
    option_side,
):
    """
    Black-Scholes delta.

    Call = positive delta
    Put  = negative delta
    """

    if (
        spot <= 0
        or strike <= 0
        or years <= 0
        or iv <= 0
    ):
        return None

    d1 = (
        math.log(spot / strike)
        + (
            risk_free
            + 0.5 * iv ** 2
        ) * years
    ) / (
        iv * math.sqrt(years)
    )

    n_d1 = norm_cdf(d1)

    if option_side == "call":
        return n_d1

    return n_d1 - 1


def round_otm_strike(
    value,
    increment,
    side,
):
    """
    Round a strike further OTM.

    Put:
        floor

    Call:
        ceil
    """

    if increment <= 0:
        return round(value, 2)

    steps = value / increment

    if side == "put":
        steps = math.floor(steps)
    else:
        steps = math.ceil(steps)

    return round(
        steps * increment,
        2,
    )


def get_next_earnings_date(ticker):
    """
    Best-effort Yahoo Finance earnings lookup.
    """

    try:

        tk = yf.Ticker(ticker)

        try:

            earnings = tk.get_earnings_dates(
                limit=8
            )

            if (
                earnings is not None
                and not earnings.empty
            ):

                today = pd.Timestamp(
                    date.today()
                )

                index = earnings.index

                if getattr(
                    index,
                    "tz",
                    None,
                ) is not None:

                    index = index.tz_localize(
                        None
                    )

                future = earnings.loc[
                    index >= today
                ]

                if not future.empty:

                    first = future.index[0]

                    if getattr(
                        first,
                        "tz",
                        None,
                    ) is not None:

                        first = first.tz_localize(
                            None
                        )

                    return first.date()

        except Exception:
            pass

        try:

            calendar = tk.calendar

            if isinstance(
                calendar,
                dict,
            ):

                dates = calendar.get(
                    "Earnings Date"
                )

                if dates:
                    return pd.Timestamp(
                        dates[0]
                    ).date()

            elif hasattr(
                calendar,
                "loc",
            ):

                value = calendar.loc[
                    "Earnings Date"
                ].iloc[0]

                return pd.Timestamp(
                    value
                ).date()

        except Exception:
            pass

    except Exception:
        pass

    return None


# ============================================================
# SECTION 0 — MARKET DATA
# ============================================================

st.header("0. Market Data")

ticker = st.text_input(
    "Ticker",
    value="SPY",
).strip().upper()


if st.button(
    "🔄 Fetch Price & Indicators"
):

    try:

        history = (
            yf.Ticker(ticker)
            .history(
                period="1y",
                interval="1d",
            )
        )

        if history.empty:

            st.error(
                "No price history returned. "
                "Check the ticker."
            )

        else:

            close = history["Close"]
            high = history["High"]
            low = history["Low"]

            previous_close = close.shift(1)

            # ------------------------
            # PRICE
            # ------------------------

            st.session_state["price"] = round(
                float(close.iloc[-1]),
                2,
            )

            # ------------------------
            # EMAs
            # ------------------------

            for span, key in [
                (20, "ema20"),
                (50, "ema50"),
                (200, "ema200"),
            ]:

                value = (
                    close
                    .ewm(
                        span=span,
                        adjust=False,
                    )
                    .mean()
                    .iloc[-1]
                )

                st.session_state[key] = round(
                    float(value),
                    2,
                )

            # ------------------------
            # RSI
            # ------------------------

            change = close.diff()

            gain = change.clip(
                lower=0
            )

            loss = -change.clip(
                upper=0
            )

            avg_gain = gain.ewm(
                alpha=1 / 14,
                adjust=False,
            ).mean()

            avg_loss = loss.ewm(
                alpha=1 / 14,
                adjust=False,
            ).mean()

            rs = avg_gain / avg_loss.replace(
                0,
                float("nan"),
            )

            rsi_series = (
                100
                - 100 / (1 + rs)
            )

            st.session_state["rsi"] = round(
                float(rsi_series.iloc[-1]),
                1,
            )

            # ------------------------
            # MACD
            # ------------------------

            ema12 = close.ewm(
                span=12,
                adjust=False,
            ).mean()

            ema26 = close.ewm(
                span=26,
                adjust=False,
            ).mean()

            macd = ema12 - ema26

            signal = macd.ewm(
                span=9,
                adjust=False,
            ).mean()

            st.session_state[
                "macd_line"
            ] = round(
                float(macd.iloc[-1]),
                2,
            )

            st.session_state[
                "macd_signal"
            ] = round(
                float(signal.iloc[-1]),
                2,
            )

            # ------------------------
            # ATR
            # ------------------------

            true_range = pd.concat(
                [
                    high - low,
                    (
                        high
                        - previous_close
                    ).abs(),
                    (
                        low
                        - previous_close
                    ).abs(),
                ],
                axis=1,
            ).max(axis=1)

            atr = true_range.ewm(
                alpha=1 / 14,
                adjust=False,
            ).mean()

            st.session_state["atr"] = round(
                float(atr.iloc[-1]),
                2,
            )

            # ------------------------
            # EARNINGS
            # ------------------------

            earnings = (
                get_next_earnings_date(
                    ticker
                )
            )

            if earnings:

                st.session_state[
                    "next_earnings_date"
                ] = earnings.isoformat()

            else:

                st.session_state[
                    "next_earnings_date"
                ] = None

            # Clear old option data

            st.session_state[
                "expirations"
            ] = []

            st.session_state[
                "chain_df"
            ] = None

            st.session_state[
                "atm_iv"
            ] = 20.0

            st.session_state[
                "chain_version"
            ] += 1

            st.session_state[
                "data_fetched_at"
            ] = datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )

            st.success(
                f"Fetched {ticker} — "
                f"latest bar "
                f"{history.index[-1].date()}"
            )

    except Exception as exc:

        st.error(
            f"Fetch failed: {exc}"
        )


if st.session_state[
    "data_fetched_at"
]:

    st.caption(
        "Last fetched: "
        + st.session_state[
            "data_fetched_at"
        ]
    )

    earnings = st.session_state[
        "next_earnings_date"
    ]

    if earnings:

        st.caption(
            f"Approx. next earnings: "
            f"{earnings}"
        )


# ============================================================
# SECTION 1 — TREND
# ============================================================

st.header("1. Trend")

col1, col2, col3 = st.columns(3)

with col1:

    price = st.number_input(
        "Current price",
        min_value=0.01,
        value=float(
            st.session_state[
                "price"
            ]
        ),
        step=0.01,
        format="%.2f",
        key="price_input",
    )

with col2:

    ema20 = st.number_input(
        "EMA20",
        min_value=0.01,
        value=float(
            st.session_state[
                "ema20"
            ]
        ),
        step=0.01,
        format="%.2f",
        key="ema20_input",
    )

with col3:

    ema50 = st.number_input(
        "EMA50",
        min_value=0.01,
        value=float(
            st.session_state[
                "ema50"
            ]
        ),
        step=0.01,
        format="%.2f",
        key="ema50_input",
    )


ema200 = st.number_input(
    "EMA200",
    min_value=0.01,
    value=float(
        st.session_state[
            "ema200"
        ]
    ),
    step=0.01,
    format="%.2f",
    key="ema200_input",
)


# ============================================================
# DIRECTION
# ============================================================

if price > ema20:

    direction = "Bull Put Spread"
    side = "put"
    option_type = "PUT"

    st.success(
        f"Price ${price:.2f} > EMA20 "
        f"${ema20:.2f} → "
        f"**BULL PUT SPREAD**"
    )

elif price < ema20:

    direction = "Bear Call Spread"
    side = "call"
    option_type = "CALL"

    st.error(
        f"Price ${price:.2f} < EMA20 "
        f"${ema20:.2f} → "
        f"**BEAR CALL SPREAD**"
    )

else:

    direction = None
    side = None
    option_type = None

    st.warning(
        "Price equals EMA20. "
        "There is no clear directional signal."
    )


# ============================================================
# MOMENTUM CONTEXT
# ============================================================

st.subheader(
    "Momentum Context"
)

st.caption(
    "RSI and MACD help describe trend strength. "
    "They do NOT automatically reject the trade."
)

col4, col5, col6 = st.columns(3)

with col4:

    rsi = st.number_input(
        "RSI (14)",
        min_value=0.0,
        max_value=100.0,
        value=float(
            st.session_state["rsi"]
        ),
        step=0.5,
    )

with col5:

    macd_line = st.number_input(
        "MACD line",
        value=float(
            st.session_state[
                "macd_line"
            ]
        ),
        step=0.01,
        format="%.2f",
    )

with col6:

    macd_signal = st.number_input(
        "MACD signal",
        value=float(
            st.session_state[
                "macd_signal"
            ]
        ),
        step=0.01,
        format="%.2f",
    )


macd_histogram = (
    macd_line
    - macd_signal
)


# ============================================================
# TREND STRENGTH
# ============================================================

def trend_strength_score(
    side,
    price,
    ema20,
    ema50,
    ema200,
    rsi,
    macd_line,
    macd_signal,
):

    score = 0

    notes = []

    # ------------------------
    # EMA
    # ------------------------

    if side == "put":

        if ema20 > ema50 > ema200:

            score += 2
            notes.append(
                "Strong bullish EMA stack"
            )

        elif ema20 > ema50:

            score += 1
            notes.append(
                "Partial bullish EMA stack"
            )

        else:

            notes.append(
                "EMA stack not bullish"
            )

    elif side == "call":

        if ema20 < ema50 < ema200:

            score += 2
            notes.append(
                "Strong bearish EMA stack"
            )

        elif ema20 < ema50:

            score += 1
            notes.append(
                "Partial bearish EMA stack"
            )

        else:

            notes.append(
                "EMA stack not bearish"
            )

    # ------------------------
    # RSI
    # ------------------------

    if side == "put":

        if 50 <= rsi <= 70:

            score += 2
            notes.append(
                "RSI supports bullish trend"
            )

        elif 40 <= rsi <= 80:

            score += 1
            notes.append(
                "RSI is neutral/borderline"
            )

        else:

            notes.append(
                "RSI is weak/extended"
            )

    elif side == "call":

        if 30 <= rsi <= 50:

            score += 2
            notes.append(
                "RSI supports bearish trend"
            )

        elif 20 <= rsi <= 60:

            score += 1
            notes.append(
                "RSI is neutral/borderline"
            )

        else:

            notes.append(
                "RSI is weak/extended"
            )

    # ------------------------
    # MACD
    # ------------------------

    if side == "put":

        if macd_line > macd_signal:

            score += 2
            notes.append(
                "MACD bullish"
            )

        else:

            score += 0
            notes.append(
                "MACD bearish"
            )

    elif side == "call":

        if macd_line < macd_signal:

            score += 2
            notes.append(
                "MACD bearish"
            )

        else:

            score += 0
            notes.append(
                "MACD bullish"
            )

    return score, notes


score, trend_notes = trend_strength_score(
    side,
    price,
    ema20,
    ema50,
    ema200,
    rsi,
    macd_line,
    macd_signal,
)


if score >= 5:

    trend_strength = "Strong"

elif score >= 3:

    trend_strength = "Average"

else:

    trend_strength = "Choppy / Uncertain"


st.metric(
    "Trend Strength",
    trend_strength,
    f"{score}/6",
)

with st.expander(
    "Trend context"
):

    for note in trend_notes:

        st.write(
            f"• {note}"
        )


# ============================================================
# SECTION 2 — ATR
# ============================================================

st.header(
    "2. Distance — ATR Reality Check"
)

col_atr, col_increment = st.columns(2)

with col_atr:

    atr = st.number_input(
        "ATR (14-day)",
        min_value=0.01,
        value=float(
            st.session_state["atr"]
        ),
        step=0.01,
        format="%.2f",
    )

with col_increment:

    strike_increment = st.number_input(
        "Strike increment ($)",
        min_value=0.01,
        value=1.0,
        step=0.5,
    )


if trend_strength == "Strong":

    low_atr = 1.0
    high_atr = 2.0

elif trend_strength == "Average":

    low_atr = 2.0
    high_atr = 2.0

else:

    low_atr = 2.0
    high_atr = 3.0


st.info(
    f"OTM Flex ATR guideline: "
    f"**{low_atr:.1f}–{high_atr:.1f} ATR** "
    f"for a {trend_strength.lower()} trend."
)


# ============================================================
# ATR LADDER
# ============================================================

atr_ladder = []

if side:

    for multiplier in [
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ]:

        if side == "put":

            strike = round_otm_strike(
                price - atr * multiplier,
                strike_increment,
                "put",
            )

            distance = (
                price - strike
            )

        else:

            strike = round_otm_strike(
                price + atr * multiplier,
                strike_increment,
                "call",
            )

            distance = (
                strike - price
            )

        actual_atr = (
            distance / atr
            if atr > 0
            else 0
        )

        within = (
            low_atr
            <= actual_atr
            <= high_atr
        )

        atr_ladder.append(
            {
                "Target ATR":
                    f"{multiplier:.1f}x",

                "Strike":
                    strike,

                "Distance":
                    round(
                        distance,
                        2,
                    ),

                "Actual ATR":
                    round(
                        actual_atr,
                        2,
                    ),

                "Guideline":
                    "✅"
                    if within
                    else "",
            }
        )


if atr_ladder:

    st.dataframe(
        pd.DataFrame(
            atr_ladder
        ),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# SECTION 3 — OPTION CHAIN
# ============================================================

st.header(
    "3. Strike Selection — "
    "Delta → Distance → Flex"
)

if side:

    st.caption(
        "The option chain identifies the "
        "0.10–0.18 delta starting point. "
        "The Flex ladder then moves farther OTM."
    )

    risk_free_pct = st.number_input(
        "Risk-free rate (%)",
        min_value=0.0,
        max_value=15.0,
        value=4.30,
        step=0.05,
    )

    risk_free = (
        risk_free_pct / 100
    )


    # ========================================================
    # LOAD EXPIRATIONS
    # ========================================================

    if st.button(
        "📅 Load Expirations"
    ):

        try:

            st.session_state[
                "expirations"
            ] = list(
                yf.Ticker(
                    ticker
                ).options
            )

        except Exception as exc:

            st.error(
                f"Could not load expirations: "
                f"{exc}"
            )


    expirations = st.session_state[
        "expirations"
    ]


    if expirations:

        today = date.today()

        expiration_labels = []

        for expiration in expirations:

            try:

                dte = (
                    date.fromisoformat(
                        expiration
                    )
                    - today
                ).days

                expiration_labels.append(
                    f"{expiration} "
                    f"({dte} DTE)"
                )

            except ValueError:

                expiration_labels.append(
                    expiration
                )


        selected_label = st.selectbox(
            "Expiration",
            expiration_labels,
        )

        selected_expiration = expirations[
            expiration_labels.index(
                selected_label
            )
        ]


        if st.button(
            "📊 Fetch Option Chain"
        ):

            try:

                chain = (
                    yf.Ticker(
                        ticker
                    ).option_chain(
                        selected_expiration
                    )
                )

                chain_data = (
                    chain.puts
                    if side == "put"
                    else chain.calls
                )


                expiration_date = (
                    date.fromisoformat(
                        selected_expiration
                    )
                )

                days_to_expiration = (
                    expiration_date
                    - today
                ).days

                years = (
                    max(
                        days_to_expiration,
                        0,
                    )
                    / 365
                )


                # ------------------------------------------
                # ATM IV
                # ------------------------------------------

                if not chain_data.empty:

                    nearest_index = (
                        (
                            chain_data[
                                "strike"
                            ]
                            - price
                        )
                        .abs()
                        .argsort()
                        .iloc[0]
                    )

                    atm_row = chain_data.iloc[
                        nearest_index
                    ]

                    atm_iv = atm_row.get(
                        "impliedVolatility"
                    )

                    if (
                        atm_iv
                        and atm_iv > 0
                    ):

                        st.session_state[
                            "atm_iv"
                        ] = round(
                            float(atm_iv)
                            * 100,
                            1,
                        )

                        st.session_state[
                            "atm_iv_dte"
                        ] = (
                            days_to_expiration
                        )


                # ------------------------------------------
                # BUILD CHAIN TABLE
                # ------------------------------------------

                rows = []

                for _, row in chain_data.iterrows():

                    strike = row.get(
                        "strike"
                    )

                    iv = row.get(
                        "impliedVolatility"
                    )

                    if (
                        strike is None
                        or iv is None
                        or iv <= 0
                        or years <= 0
                    ):
                        continue


                    # Only OTM strikes

                    if (
                        side == "put"
                        and strike >= price
                    ):
                        continue

                    if (
                        side == "call"
                        and strike <= price
                    ):
                        continue


                    delta = bs_delta(
                        price,
                        strike,
                        years,
                        risk_free,
                        iv,
                        side,
                    )

                    if delta is None:
                        continue


                    abs_delta = abs(
                        delta
                    )


                    # Keep a wider range
                    # to show Flex strikes.

                    if (
                        abs_delta < 0.03
                        or abs_delta > 0.40
                    ):
                        continue


                    bid = float(
                        row.get(
                            "bid"
                        )
                        or 0
                    )

                    ask = float(
                        row.get(
                            "ask"
                        )
                        or 0
                    )

                    mid = (
                        (bid + ask) / 2
                        if bid > 0
                        and ask > 0
                        else 0
                    )


                    spread = (
                        ask - bid
                        if ask > 0
                        and bid > 0
                        else 0
                    )


                    rows.append(
                        {
                            "Strike":
                                round(
                                    float(
                                        strike
                                    ),
                                    2,
                                ),

                            "Delta":
                                round(
                                    abs_delta,
                                    2,
                                ),

                            "IV %":
                                round(
                                    float(iv)
                                    * 100,
                                    1,
                                ),

                            "Bid":
                                round(
                                    bid,
                                    2,
                                ),

                            "Ask":
                                round(
                                    ask,
                                    2,
                                ),

                            "Mid":
                                round(
                                    mid,
                                    2,
                                ),

                            "Bid/Ask Width":
                                round(
                                    spread,
                                    2,
                                ),
                        }
                    )


                if rows:

                    chain_df = pd.DataFrame(
                        rows
                    )

                    chain_df = chain_df.sort_values(
                        "Strike",
                        ascending=(
                            side == "call"
                        ),
                    ).reset_index(
                        drop=True
                    )

                    st.session_state[
                        "chain_df"
                    ] = chain_df

                    st.session_state[
                        "chain_version"
                    ] += 1

                    st.success(
                        f"Loaded "
                        f"{len(chain_df)} "
                        f"OTM strikes."
                    )

                else:

                    st.warning(
                        "No usable OTM strikes "
                        "were found."
                    )

            except Exception as exc:

                st.error(
                    f"Option chain fetch failed: "
                    f"{exc}"
                )

    else:

        st.caption(
            "Click Load Expirations first."
        )


# ============================================================
# MANUAL CHAIN
# ============================================================

chain_df = st.session_state[
    "chain_df"
]


if chain_df is None:

    manual_strikes = []

    for multiplier in [
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ]:

        if side == "put":

            strike = round_otm_strike(
                price - atr * multiplier,
                strike_increment,
                "put",
            )

        else:

            strike = round_otm_strike(
                price + atr * multiplier,
                strike_increment,
                "call",
            )

        manual_strikes.append(
            strike
        )


    chain_df = pd.DataFrame(
        {
            "Strike":
                manual_strikes,

            "Delta":
                [
                    0.22,
                    0.18,
                    0.14,
                    0.11,
                    0.08,
                ],

            "Bid":
                [0.0] * 5,

            "Ask":
                [0.0] * 5,

            "Mid":
                [0.0] * 5,
        }
    )


edited_chain = st.data_editor(
    chain_df,
    num_rows="dynamic",
    use_container_width=True,
    key=(
        "chain_editor_"
        + str(
            st.session_state[
                "chain_version"
            ]
        )
    ),
    column_config={
        "Strike":
            st.column_config.NumberColumn(
                format="%.2f",
                min_value=0.01,
                step=0.50,
            ),

        "Delta":
            st.column_config.NumberColumn(
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
            ),

        "Bid":
            st.column_config.NumberColumn(
                format="$%.2f",
                min_value=0.0,
                step=0.01,
            ),

        "Ask":
            st.column_config.NumberColumn(
                format="$%.2f",
                min_value=0.0,
                step=0.01,
            ),

        "Mid":
            st.column_config.NumberColumn(
                format="$%.2f",
                min_value=0.0,
                step=0.01,
            ),
    },
)


# ============================================================
# CANDIDATE ANALYSIS
# ============================================================

if side and not edited_chain.empty:

    candidates = []

    for _, row in edited_chain.iterrows():

        try:

            strike = float(
                row["Strike"]
            )

            delta = float(
                row["Delta"]
            )

        except (
            ValueError,
            TypeError,
        ):

            continue


        # --------------------------------------
        # Ensure OTM
        # --------------------------------------

        if side == "put":

            if strike >= price:
                continue

            distance = (
                price - strike
            )

        else:

            if strike <= price:
                continue

            distance = (
                strike - price
            )


        atr_multiple = (
            distance / atr
            if atr > 0
            else 0
        )


        delta_target = (
            0.10
            <= delta
            <= 0.18
        )


        distance_target = (
            low_atr
            <= atr_multiple
            <= high_atr
        )


        # --------------------------------------
        # Credit
        # --------------------------------------

        mid = float(
            row.get(
                "Mid",
                0,
            )
            or 0
        )


        bid = float(
            row.get(
                "Bid",
                0,
            )
            or 0
        )


        ask = float(
            row.get(
                "Ask",
                0,
            )
            or 0
        )


        # --------------------------------------
        # FLEX CATEGORY
        # --------------------------------------

        if delta_target:

            if distance_target:

                status = (
                    "⭐ Preferred"
                )

            else:

                status = (
                    "🟢 Delta OK — "
                    "check distance"
                )

        elif delta > 0.18:

            status = (
                "🟡 Move further OTM"
            )

        elif delta < 0.10:

            status = (
                "⚪ More conservative"
            )

        else:

            status = (
                "⚪ Review"
            )


        candidates.append(
            {
                "Strike":
                    strike,

                "Delta":
                    delta,

                "Distance":
                    round(
                        distance,
                        2,
                    ),

                "ATR":
                    round(
                        atr_multiple,
                        2,
                    ),

                "Delta 0.10–0.18":
                    "✅"
                    if delta_target
                    else "",

                "ATR Guideline":
                    "✅"
                    if distance_target
                    else "",

                "Mid Credit":
                    round(
                        mid,
                        2,
                    ),

                "Status":
                    status,
            }
        )


    candidate_df = pd.DataFrame(
        candidates
    )


    st.subheader(
        "OTM Flex Candidate Ladder"
    )

    st.dataframe(
        candidate_df,
        hide_index=True,
        use_container_width=True,
    )


    # ========================================================
    # GOLDEN RULE SELECTION
    # ========================================================

    preferred = candidate_df[
        (
            candidate_df[
                "Delta 0.10–0.18"
            ]
            == "✅"
        )
        &
        (
            candidate_df[
                "ATR Guideline"
            ]
            == "✅"
        )
    ]


    if not preferred.empty:

        if side == "put":

            best_index = preferred[
                "Strike"
            ].idxmax()

        else:

            best_index = preferred[
                "Strike"
            ].idxmin()


        best = preferred.loc[
            best_index
        ]


        st.success(
            f"⭐ **OTM Flex Starting Strike: "
            f"{best['Strike']:.2f}**"
        )

        st.write(
            f"Delta: **{best['Delta']:.2f}**  |  "
            f"Distance: **${best['Distance']:.2f}**  |  "
            f"ATR: **{best['ATR']:.2f}x**"
        )

        st.caption(
            "This is the closest strike that "
            "satisfies both the preferred "
            "delta range and ATR guideline."
        )

    else:

        st.warning(
            "No strike currently satisfies "
            "both the preferred delta and "
            "ATR guideline."
        )

        st.info(
            "OTM Flex does NOT automatically "
            "mean 'no trade.' Review the ladder "
            "and move further OTM if needed."
        )


    # ========================================================
    # FLEX LADDER
    # ========================================================

    st.subheader(
        "🔄 Flex Ladder"
    )

    st.caption(
        "If the starting strike feels too risky, "
        "move down for puts or up for calls."
    )


    sorted_candidates = candidate_df.copy()


    if side == "put":

        sorted_candidates = (
            sorted_candidates
            .sort_values(
                "Strike",
                ascending=False,
            )
        )

    else:

        sorted_candidates = (
            sorted_candidates
            .sort_values(
                "Strike",
                ascending=True,
            )
        )


    flex_rows = []

    for position, (_, row) in enumerate(
        sorted_candidates.iterrows()
    ):

        if position == 0:

            flex_action = (
                "Starting point"
            )

        else:

            flex_action = (
                f"Flex #{position} — "
                "further OTM"
            )

        flex_rows.append(
            {
                "Step":
                    position,

                "Strike":
                    row["Strike"],

                "Delta":
                    row["Delta"],

                "ATR":
                    row["ATR"],

                "Credit":
                    row["Mid Credit"],

                "Action":
                    flex_action,
            }
        )


    st.dataframe(
        pd.DataFrame(
            flex_rows
        ),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# SECTION 4 — EXPIRATION
# ============================================================

st.header(
    "4. Expiration"
)

dte = st.slider(
    "Days to expiration",
    min_value=1,
    max_value=60,
    value=21,
)


if 7 <= dte <= 45:

    st.success(
        f"{dte} DTE is inside the "
        f"OTM Flex 7–45 DTE range."
    )

else:

    st.warning(
        f"{dte} DTE is outside the "
        f"typical 7–45 DTE range."
    )


expiration_estimate = (
    date.today()
    + timedelta(days=dte)
)


# ============================================================
# EARNINGS
# ============================================================

st.subheader(
    "📅 Earnings Check"
)

earnings_string = st.session_state[
    "next_earnings_date"
]


if earnings_string:

    earnings_date = date.fromisoformat(
        earnings_string
    )

    st.write(
        f"Next approximate earnings: "
        f"**{earnings_date}**"
    )

    st.write(
        f"Estimated expiration: "
        f"**{expiration_estimate}**"
    )


    if (
        date.today()
        <= earnings_date
        <= expiration_estimate
    ):

        st.error(
            "⚠️ Earnings occur before "
            "this expiration. "
            "OTM Flex Rule 11: avoid "
            "holding the stock spread "
            "through earnings."
        )

    else:

        st.success(
            "No earnings date falls "
            "inside this expiration window."
        )

else:

    st.warning(
        "Earnings date unavailable. "
        "Verify your broker's earnings calendar."
    )


# ============================================================
# SECTION 5 — EXPECTED MOVE
# ============================================================

st.header(
    "5. Expected Move — IV Reality Check"
)

st.caption(
    "Expected move is another reality check. "
    "It does not replace ATR or Delta."
)


atm_iv = st.number_input(
    "ATM implied volatility (%)",
    min_value=0.1,
    max_value=300.0,
    value=float(
        st.session_state[
            "atm_iv"
        ]
    ),
    step=0.5,
)


expected_move = (
    price
    * (atm_iv / 100)
    * math.sqrt(
        dte / 365
    )
)


expected_atr = (
    expected_move / atr
    if atr > 0
    else 0
)


col_em1, col_em2 = st.columns(2)

with col_em1:

    st.metric(
        "Expected Move",
        f"±${expected_move:.2f}",
    )

with col_em2:

    st.metric(
        "Expected Move / ATR",
        f"{expected_atr:.2f}x",
    )


st.caption(
    "If the expected move is substantially "
    "larger than the distance to your short "
    "strike, consider using the Flex rule "
    "and moving further OTM."
)


# ============================================================
# SECTION 6 — CREDIT
# ============================================================

st.header(
    "6. Credit & Profit Target"
)

col_credit, col_width = st.columns(2)

with col_credit:

    credit = st.number_input(
        "Credit received ($/spread)",
        min_value=0.0,
        value=1.00,
        step=0.01,
        format="%.2f",
    )

with col_width:

    width = st.number_input(
        "Spread width ($)",
        min_value=0.01,
        value=5.00,
        step=0.50,
        format="%.2f",
    )


max_loss = max(
    width - credit,
    0,
)


profit_target = (
    credit * 0.50
)


roc = (
    credit / max_loss * 100
    if max_loss > 0
    else 0
)


col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Max Loss",
        f"${max_loss:.2f}",
    )

with col2:

    st.metric(
        "50% Buyback",
        f"${profit_target:.2f}",
    )

with col3:

    st.metric(
        "ROC",
        f"{roc:.1f}%",
    )


# ============================================================
# CREDIT QUALITY
# ============================================================

st.subheader(
    "Credit Requirement"
)

min_credit = st.number_input(
    "Minimum acceptable credit ($)",
    min_value=0.00,
    value=0.50,
    step=0.05,
    format="%.2f",
)


credit_ok = (
    credit >= min_credit
)


if credit_ok:

    st.success(
        f"Credit requirement passes: "
        f"${credit:.2f} ≥ ${min_credit:.2f}"
    )

else:

    st.warning(
        f"Credit below your minimum: "
        f"${credit:.2f} < ${min_credit:.2f}"
    )


# ============================================================
# SECTION 7 — LIQUIDITY
# ============================================================

st.header(
    "7. Liquidity Check"
)

st.caption(
    "Liquidity is a practical requirement, "
    "not a directional filter."
)


bid = st.number_input(
    "Short-strike bid",
    min_value=0.0,
    value=0.00,
    step=0.01,
    format="%.2f",
)

ask = st.number_input(
    "Short-strike ask",
    min_value=0.0,
    value=0.00,
    step=0.01,
    format="%.2f",
)


if bid > 0 and ask >= bid:

    bid_ask_width = (
        ask - bid
    )

    mid = (
        bid + ask
    ) / 2

    spread_pct = (
        bid_ask_width / mid * 100
        if mid > 0
        else 0
    )

    st.write(
        f"Bid/ask width: "
        f"**${bid_ask_width:.2f}**"
    )

    st.write(
        f"Spread width as % of mid: "
        f"**{spread_pct:.1f}%**"
    )

    if spread_pct <= 10:

        st.success(
            "Liquidity looks reasonable."
        )

    elif spread_pct <= 20:

        st.warning(
            "Liquidity is getting wider. "
            "Use caution with fills."
        )

    else:

        st.warning(
            "Wide bid/ask spread. "
            "Consider a more liquid strike "
            "or underlying."
        )

else:

    st.caption(
        "Enter bid and ask to evaluate liquidity."
    )


# ============================================================
# SECTION 8 — POSITION SIZING
# ============================================================

st.header(
    "8. Position Sizing"
)

account_size = st.number_input(
    "Account size ($)",
    min_value=0.0,
    value=20000.0,
    step=500.0,
    format="%.2f",
)


risk_pct = st.number_input(
    "Risk per trade (%)",
    min_value=0.1,
    max_value=100.0,
    value=2.0,
    step=0.5,
)


max_risk_dollars = (
    account_size
    * risk_pct
    / 100
)


contracts = (
    int(
        max_risk_dollars
        // max_loss
    )
    if max_loss > 0
    else 0
)


actual_risk = (
    contracts
    * max_loss
)


actual_risk_pct = (
    actual_risk
    / account_size
    * 100
    if account_size > 0
    else 0
)


col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Risk Budget",
        f"${max_risk_dollars:,.0f}",
    )

with col2:

    st.metric(
        "Max Contracts",
        contracts,
    )

with col3:

    st.metric(
        "Actual Max Risk",
        f"${actual_risk:,.0f}",
    )


if contracts == 0:

    st.warning(
        "One spread exceeds your selected "
        "risk budget."
    )

else:

    st.success(
        f"{contracts} contract(s) fit within "
        f"your {risk_pct:.1f}% risk budget."
    )


# ============================================================
# POSITION SIZE TABLE
# ============================================================

st.subheader(
    "Risk-Level Reference"
)

risk_levels = [
    1,
    2,
    3,
    5,
    10,
    15,
    20,
]


sizing_rows = []

for risk_level in risk_levels:

    dollars = (
        account_size
        * risk_level
        / 100
    )

    possible_contracts = (
        int(
            dollars
            // max_loss
        )
        if max_loss > 0
        else 0
    )

    sizing_rows.append(
        {
            "Risk %":
                f"{risk_level}%",

            "Risk Budget":
                f"${dollars:,.0f}",

            "Contracts":
                possible_contracts,

            "Max Loss":
                f"$"
                f"{possible_contracts * max_loss:,.0f}",
        }
    )


st.dataframe(
    pd.DataFrame(
        sizing_rows
    ),
    hide_index=True,
    use_container_width=True,
)


# ============================================================
# SECTION 9 — TRADE MANAGEMENT
# ============================================================

st.header(
    "9. Trade Management"
)

st.subheader(
    "Profit Target"
)

st.success(
    f"Initial profit target: "
    f"buy back around **${profit_target:.2f}** "
    f"if you collected ${credit:.2f}."
)


st.subheader(
    "Threatened Trade Checklist"
)

st.markdown(
    """
Before rolling or adjusting a threatened spread:

☐ Is the original EMA20 trend still intact?

☐ Has the short-strike delta increased materially?

☐ Is the short strike still sufficiently OTM?

☐ Has the expected move changed?

☐ Has volatility increased?

☐ Is there still enough time to expiration?

☐ Would moving further OTM reduce risk?

☐ Would closing the position preserve more capital?

☐ If rolling, does the new trade actually improve the risk?
"""
)


# ============================================================
# FINAL OTM FLEX DASHBOARD
# ============================================================

st.divider()

st.header(
    "🎯 OTM Flex™ Trade Dashboard"
)


if side:

    dashboard_rows = [
        {
            "Rule":
                "Direction",

            "Result":
                direction,

            "Status":
                "✅",
        },
        {
            "Rule":
                "Delta",

            "Result":
                "Target 0.10–0.18",

            "Status":
                "🎯",
        },
        {
            "Rule":
                "ATR",

            "Result":
                f"{low_atr:.1f}–{high_atr:.1f}x",

            "Status":
                "📏",
        },
        {
            "Rule":
                "DTE",

            "Result":
                f"{dte} DTE",

            "Status":
                (
                    "✅"
                    if 7 <= dte <= 45
                    else "⚠️"
                ),
        },
        {
            "Rule":
                "Credit",

            "Result":
                f"${credit:.2f}",

            "Status":
                (
                    "✅"
                    if credit_ok
                    else "⚠️"
                ),
        },
        {
            "Rule":
                "Profit Target",

            "Result":
                f"${profit_target:.2f}",

            "Status":
                "🎯",
        },
        {
            "Rule":
                "Earnings",

            "Result":
                (
                    "Inside expiration"
                    if earnings_string
                    and
                    date.today()
                    <= date.fromisoformat(
                        earnings_string
                    )
                    <= expiration_estimate
                    else "Clear / verify"
                ),

            "Status":
                (
                    "⚠️"
                    if earnings_string
                    and
                    date.today()
                    <= date.fromisoformat(
                        earnings_string
                    )
                    <= expiration_estimate
                    else "✅"
                ),
        },
        {
            "Rule":
                "Position Size",

            "Result":
                f"{contracts} contract(s)",

            "Status":
                "📊",
        },
    ]


    st.dataframe(
        pd.DataFrame(
            dashboard_rows
        ),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# FLEX REMINDER
# ============================================================

st.divider()

st.success(
    "🟢 OTM FLEX RULE: "
    "When in doubt, go further OTM — "
    "not out of the trade."
)

st.caption(
    "Trend determines direction. "
    "Distance determines safety. "
    "Flexibility determines consistency."
)
