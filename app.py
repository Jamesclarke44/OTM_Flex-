"""
OTM Flex - Credit Spread Strike Selection Calculator

A Streamlit tool that implements the OTM Flex rule book:
trend -> delta -> distance -> flex.

Includes an optional free auto-fetch (Yahoo Finance via yfinance) for
price/EMA/RSI/MACD/ATR and a Black-Scholes delta estimate built from the
free (delayed) option chain's implied volatility. Everything stays
manually editable either way.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import date, datetime, timedelta
import math

import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="OTM Flex Calculator", page_icon="📉", layout="centered")

st.title("📉 OTM Flex — Strike Selection Calculator")
st.caption(
    "Trend → Delta → Distance → Flex. Auto-fetch is free (delayed, via Yahoo Finance); "
    "every field stays manually editable."
)

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
# Shared math helpers
# ---------------------------------------------------------------------------
def norm_cdf(x):
    """Standard normal CDF, no scipy dependency needed."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_delta(spot, strike, years_to_exp, risk_free, iv, option_side):
    """Black-Scholes delta. option_side is 'put' or 'call'. Returns signed delta."""
    if years_to_exp <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return None
    d1 = (math.log(spot / strike) + (risk_free + 0.5 * iv ** 2) * years_to_exp) / (
        iv * math.sqrt(years_to_exp)
    )
    n_d1 = norm_cdf(d1)
    return n_d1 if option_side == "call" else n_d1 - 1


def round_to_increment(value, increment, option_side):
    """Round to the nearest real strike, biased further OTM (floor for puts, ceil for calls)."""
    if increment <= 0:
        return round(value, 2)
    steps = value / increment
    steps = math.floor(steps) if option_side == "put" else math.ceil(steps)
    return round(steps * increment, 2)


def get_next_earnings_date(ticker_symbol):
    """Best-effort free lookup of the next earnings date. Returns a date or None.

    yfinance's earnings-date API has changed across versions, so this tries
    a couple of approaches and quietly gives up rather than crashing the app.
    """
    try:
        tk = yf.Ticker(ticker_symbol)
        try:
            edf = tk.get_earnings_dates(limit=8)
            if edf is not None and not edf.empty:
                today_ts = pd.Timestamp(date.today())
                idx = edf.index
                idx_naive = idx.tz_localize(None) if idx.tz is not None else idx
                future = edf.loc[idx_naive >= today_ts]
                if not future.empty:
                    return future.index[0].date() if future.index[0].tz is None else future.index[0].tz_localize(None).date()
        except Exception:
            pass
        try:
            cal = tk.calendar
            if isinstance(cal, dict) and cal.get("Earnings Date"):
                d = cal["Earnings Date"][0]
                return d if isinstance(d, date) and not isinstance(d, datetime) else pd.Timestamp(d).date()
            elif hasattr(cal, "loc"):
                d = cal.loc["Earnings Date"].iloc[0]
                return pd.Timestamp(d).date()
        except Exception:
            pass
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 0. Auto-Fetch Market Data (optional, free via Yahoo Finance)
# ---------------------------------------------------------------------------
st.header("0. Auto-Fetch Market Data (optional)")
st.caption("Free, delayed ~15–20 min via Yahoo Finance. Values below are pre-filled but stay editable.")

ticker = st.text_input("Ticker", value="SPY", key="ticker").strip().upper()

if st.button("Fetch price & indicators"):
    try:
        hist = yf.Ticker(ticker).history(period="1y", interval="1d")
        if hist.empty:
            st.error("No price history returned for that ticker — check the symbol.")
        else:
            close = hist["Close"]
            high = hist["High"]
            low = hist["Low"]
            prev_close = close.shift(1)

            st.session_state["price"] = round(float(close.iloc[-1]), 2)
            st.session_state["ema20"] = round(float(close.ewm(span=20, adjust=False).mean().iloc[-1]), 2)
            st.session_state["ema50"] = round(float(close.ewm(span=50, adjust=False).mean().iloc[-1]), 2)
            st.session_state["ema200"] = round(float(close.ewm(span=200, adjust=False).mean().iloc[-1]), 2)

            delta_series = close.diff()
            gain = delta_series.clip(lower=0)
            loss = -delta_series.clip(upper=0)
            avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            rsi_series = 100 - (100 / (1 + rs))
            st.session_state["rsi"] = round(float(rsi_series.iloc[-1]), 1) if not rsi_series.empty else 50.0

            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_series = ema12 - ema26
            signal_series = macd_series.ewm(span=9, adjust=False).mean()
            st.session_state["macd_line"] = round(float(macd_series.iloc[-1]), 2)
            st.session_state["macd_signal"] = round(float(signal_series.iloc[-1]), 2)

            true_range = pd.concat(
                [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
            ).max(axis=1)
            atr_series = true_range.ewm(alpha=1 / 14, adjust=False).mean()
            st.session_state["atr"] = round(float(atr_series.iloc[-1]), 2)

            next_earnings = get_next_earnings_date(ticker)
            st.session_state["next_earnings_date"] = next_earnings.isoformat() if next_earnings else None

            st.session_state["data_fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state.pop("expirations", None)  # force reload for new ticker
            st.session_state.pop("delta_source_df", None)  # clear stale chain data
            st.session_state.pop("atm_iv", None)  # clear stale IV from a previous ticker
            st.success(f"Fetched {ticker} — latest bar {hist.index[-1].date()}")
    except Exception as exc:  # noqa: BLE001 - surface any fetch problem to the user
        st.error(f"Fetch failed: {exc}")

if st.session_state.get("data_fetched_at"):
    st.caption(f"Last fetched: {st.session_state['data_fetched_at']} for {ticker}")
    if st.session_state.get("next_earnings_date"):
        st.caption(f"Next earnings (approx, per Yahoo Finance): {st.session_state['next_earnings_date']}")
    else:
        st.caption("Next earnings date not available for this ticker from Yahoo Finance.")

# ---------------------------------------------------------------------------
# 1. Trend
# ---------------------------------------------------------------------------
st.header("1. Trend")

col1, col2, col3 = st.columns(3)
with col1:
    price = st.number_input(
        "Current price", min_value=0.01, value=st.session_state.get("price", 100.00),
        step=0.01, format="%.2f", key="price",
    )
with col2:
    ema20 = st.number_input(
        "EMA20", min_value=0.01, value=st.session_state.get("ema20", 98.00),
        step=0.01, format="%.2f", key="ema20",
    )
with col3:
    ema50 = st.number_input(
        "EMA50", min_value=0.01, value=st.session_state.get("ema50", 96.00),
        step=0.01, format="%.2f", key="ema50",
    )

ema200 = st.number_input(
    "EMA200", min_value=0.01, value=st.session_state.get("ema200", 90.00),
    step=0.01, format="%.2f", key="ema200",
)

if price > ema20:
    direction = "Bull Put Spread"
    side = "put"
    option_type = "PUT"
    st.success(f"Price is above EMA20 → **{direction}**")
elif price < ema20:
    direction = "Bear Call Spread"
    side = "call"
    option_type = "CALL"
    st.error(f"Price is below EMA20 → **{direction}**")
else:
    direction = None
    side = None
    option_type = None
    st.warning("Price equals EMA20 — no clear trend signal. Consider waiting or checking a longer timeframe.")

if option_type == "PUT":
    st.markdown("### Option Type: 🟢 **PUT** — sell puts below current price")
elif option_type == "CALL":
    st.markdown("### Option Type: 🔴 **CALL** — sell calls above current price")

# ---------------------------------------------------------------------------
# 1b. Momentum inputs (feed the auto trend-strength score)
# ---------------------------------------------------------------------------
st.subheader("Momentum (for automatic trend strength)")
col4, col5, col6 = st.columns(3)
with col4:
    rsi = st.number_input(
        "RSI (14)", min_value=0.0, max_value=100.0, value=st.session_state.get("rsi", 55.0),
        step=0.5, key="rsi",
    )
with col5:
    macd_line = st.number_input(
        "MACD line", value=st.session_state.get("macd_line", 0.30),
        step=0.01, format="%.2f", key="macd_line",
    )
with col6:
    macd_signal = st.number_input(
        "MACD signal", value=st.session_state.get("macd_signal", 0.15),
        step=0.01, format="%.2f", key="macd_signal",
    )

macd_hist = macd_line - macd_signal


def score_ema_stack(option_side, e20, e50, e200):
    if option_side == "put":  # bullish stack expected
        if e20 > e50 > e200:
            return 2, "Full bullish stack (EMA20 > EMA50 > EMA200)"
        elif e20 > e50:
            return 1, "Partial bullish stack (EMA20 > EMA50, but EMA50 ≤ EMA200)"
        else:
            return 0, "No bullish stack"
    elif option_side == "call":  # bearish stack expected
        if e20 < e50 < e200:
            return 2, "Full bearish stack (EMA20 < EMA50 < EMA200)"
        elif e20 < e50:
            return 1, "Partial bearish stack (EMA20 < EMA50, but EMA50 ≥ EMA200)"
        else:
            return 0, "No bearish stack"
    return 0, "No trend direction"


def score_rsi(option_side, rsi_val):
    if option_side == "put":
        if 50 <= rsi_val <= 70:
            return 2, "RSI in healthy uptrend zone (50–70)"
        elif 40 <= rsi_val < 50 or 70 < rsi_val <= 80:
            return 1, "RSI borderline (40–50 or 70–80)"
        else:
            return 0, "RSI too weak (<40) or overextended (>80)"
    elif option_side == "call":
        if 30 <= rsi_val <= 50:
            return 2, "RSI in healthy downtrend zone (30–50)"
        elif 20 <= rsi_val < 30 or 50 < rsi_val <= 60:
            return 1, "RSI borderline (20–30 or 50–60)"
        else:
            return 0, "RSI too weak (>60) or overextended (<20)"
    return 0, "No trend direction"


def score_macd(option_side, macd_l, macd_s, macd_h):
    if option_side == "put":
        if macd_l > macd_s and macd_h > 0:
            return 2, "MACD above signal, rising histogram"
        elif macd_l > macd_s:
            return 1, "MACD above signal, but histogram flat/falling"
        else:
            return 0, "MACD below signal"
    elif option_side == "call":
        if macd_l < macd_s and macd_h < 0:
            return 2, "MACD below signal, falling histogram"
        elif macd_l < macd_s:
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
st.header(f"2. Distance — ATR Reality Check ({option_type or '—'})")

col_atr, col_inc = st.columns(2)
with col_atr:
    atr = st.number_input(
        "ATR (e.g. 14-day)", min_value=0.01, value=st.session_state.get("atr", 2.50),
        step=0.01, format="%.2f", key="atr",
    )
with col_inc:
    strike_increment = st.number_input(
        "Strike increment ($)",
        min_value=0.01,
        value=1.0,
        step=0.5,
        help="e.g. SPY = 1, many stocks = 2.5 or 5 — implied strikes are rounded to a real, tradable strike.",
    )

atr_guidance = {
    "Strong": (1.0, 2.0),
    "Average": (2.0, 2.0),
    "Choppy / uncertain": (2.0, 3.0),
}
low_mult, high_mult = atr_guidance[trend_strength]

st.write(f"Guideline for **{trend_strength}** trend: **{low_mult}–{high_mult} ATR** away from price.")

# List every real strike (at the increment above) from 1x to 3x ATR away, closest to furthest,
# so you see the whole ladder rather than just a few sample points.
atr_rows = []
if side == "put":
    near_strike = round_to_increment(price - atr * 1.0, strike_increment, side)
    far_strike = round_to_increment(price - atr * 3.0, strike_increment, side)
    s = near_strike
    while s >= far_strike:
        atr_rows.append(s)
        s = round(s - strike_increment, 2)
elif side == "call":
    near_strike = round_to_increment(price + atr * 1.0, strike_increment, side)
    far_strike = round_to_increment(price + atr * 3.0, strike_increment, side)
    s = near_strike
    while s <= far_strike:
        atr_rows.append(s)
        s = round(s + strike_increment, 2)

atr_table_rows = []
for strike in atr_rows:
    distance = abs(price - strike)
    atr_mult = distance / atr if atr else None
    in_range = (atr_mult is not None) and (low_mult <= atr_mult <= high_mult)
    atr_table_rows.append(
        {
            "Strike": strike,
            "Distance ($)": round(distance, 2),
            "ATR multiple": round(atr_mult, 2) if atr_mult is not None else "—",
            "Within guideline": "✅" if in_range else "",
        }
    )

st.dataframe(pd.DataFrame(atr_table_rows), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# 3. Delta cross-check
# ---------------------------------------------------------------------------
st.header(f"3. Delta Cross-Check ({option_type or '—'})")

strike_col_name = f"{option_type} Strike" if option_type else "Strike"

if side is not None:
    st.subheader("Auto-fill from live option chain (free, delayed)")
    st.caption(
        "Delta here is a Black-Scholes estimate from Yahoo Finance's delayed implied volatility — "
        "close enough for strike selection, but not your broker's real-time OPRA delta."
    )

    col_rf, col_load = st.columns([1, 1])
    with col_rf:
        risk_free_pct = st.number_input(
            "Risk-free rate (%)", min_value=0.0, max_value=15.0, value=4.30, step=0.05
        )
    risk_free_rate = risk_free_pct / 100

    with col_load:
        st.write("")  # vertical spacer to align button with the number input
        if st.button("Load expirations"):
            try:
                st.session_state["expirations"] = list(yf.Ticker(ticker).options)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not load expirations: {exc}")

    expirations = st.session_state.get("expirations", [])
    if expirations:
        today = date.today()
        exp_labels = []
        for exp in expirations:
            try:
                dte_e = (date.fromisoformat(exp) - today).days
                exp_labels.append(f"{exp} ({dte_e} DTE)")
            except ValueError:
                exp_labels.append(exp)
        chosen_label = st.selectbox("Expiration", exp_labels)
        chosen_exp = expirations[exp_labels.index(chosen_label)]

        if st.button(f"Fetch {option_type.lower()} chain for {chosen_exp}"):
            try:
                chain = yf.Ticker(ticker).option_chain(chosen_exp)
                chain_df = chain.puts if side == "put" else chain.calls
                years_to_exp = max((date.fromisoformat(chosen_exp) - today).days, 0) / 365

                # Capture ATM implied vol (closest strike to price) for the Expected Move calc,
                # using the full chain before filtering down to the OTM delta band below.
                if not chain_df.empty and "strike" in chain_df.columns:
                    atm_row = chain_df.iloc[(chain_df["strike"] - price).abs().argsort().iloc[0]]
                    atm_iv_val = atm_row.get("impliedVolatility")
                    if atm_iv_val and atm_iv_val > 0:
                        st.session_state["atm_iv"] = round(float(atm_iv_val) * 100, 1)
                        st.session_state["atm_iv_dte"] = round(years_to_exp * 365)

                rows = []
                for _, r in chain_df.iterrows():
                    iv = r.get("impliedVolatility")
                    strike_val = r.get("strike")
                    if iv is None or strike_val is None or iv <= 0 or years_to_exp <= 0:
                        continue
                    if side == "put" and strike_val >= price:
                        continue
                    if side == "call" and strike_val <= price:
                        continue
                    d = bs_delta(price, strike_val, years_to_exp, risk_free_rate, iv, side)
                    if d is None:
                        continue
                    abs_delta = abs(d)
                    if abs_delta < 0.03 or abs_delta > 0.35:
                        continue
                    rows.append(
                        {
                            strike_col_name: round(float(strike_val), 2),
                            "Delta": round(abs_delta, 2),
                            "IV %": round(float(iv) * 100, 1),
                            "Bid": round(float(r.get("bid") or 0), 2),
                            "Ask": round(float(r.get("ask") or 0), 2),
                        }
                    )
                if rows:
                    fetched_df = pd.DataFrame(rows).sort_values(
                        strike_col_name, ascending=(side == "call")
                    ).reset_index(drop=True)
                    st.session_state["delta_source_df"] = fetched_df
                    st.session_state["chain_fetch_count"] = st.session_state.get("chain_fetch_count", 0) + 1
                    st.success(f"Loaded {len(fetched_df)} {option_type.lower()} strikes (delta 0.03–0.35).")
                else:
                    st.warning("No strikes came back in a usable delta range — try a different expiration.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Chain fetch failed: {exc}")
    else:
        st.caption("Click \"Load expirations\" to see available dates for this ticker.")

st.caption(
    f"Table below: candidate {option_type.lower() if option_type else ''} strikes and deltas. "
    "Auto-filled rows stay fully editable, or type in your own from your broker's chain."
)

default_rows = pd.DataFrame(
    {
        strike_col_name: [
            round_to_increment(price - atr * m, strike_increment, side) if side == "put"
            else round_to_increment(price + atr * m, strike_increment, side)
            for m in [1.0, 1.5, 2.0, 2.5, 3.0]
        ],
        "Delta": [0.22, 0.18, 0.14, 0.11, 0.08],
    }
)

table_to_edit = st.session_state.get("delta_source_df", default_rows)

edited = st.data_editor(
    table_to_edit,
    num_rows="dynamic",
    use_container_width=True,
    key=f"delta_editor_{st.session_state.get('chain_fetch_count', 0)}",
    column_config={
        "Delta": st.column_config.NumberColumn(format="%.2f", min_value=0.0, max_value=1.0, step=0.01),
    },
)


def evaluate_row(row):
    delta_ok = 0.10 <= row["Delta"] <= 0.18
    if side == "put":
        distance = price - row[strike_col_name]
    elif side == "call":
        distance = row[strike_col_name] - price
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
            best = starred.loc[starred[strike_col_name].idxmax()]
        else:
            best = starred.loc[starred[strike_col_name].idxmin()]
        st.info(
            f"**Suggested {option_type} strike (golden rule — closest qualifying): {best[strike_col_name]}** "
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

expiration_estimate = date.today() + timedelta(days=dte)

st.subheader("Earnings Check (Rule 11)")
next_earnings_str = st.session_state.get("next_earnings_date")
if next_earnings_str:
    next_earnings_date = date.fromisoformat(next_earnings_str)
    st.write(
        f"Next earnings for **{ticker}** (approx, per Yahoo Finance): **{next_earnings_date.isoformat()}** "
        f"— this trade's estimated expiration: **{expiration_estimate.isoformat()}**"
    )
    if date.today() <= next_earnings_date <= expiration_estimate:
        st.error(
            "⚠️ Earnings fall inside this DTE window. Rule 11: avoid holding stock spreads through earnings."
        )
    else:
        st.success("No earnings expected before this expiration.")
else:
    st.caption(
        "Next earnings date not available — fetch price data in Section 0, or check your broker's calendar manually."
    )

st.subheader("Expected Move (IV-based)")
st.caption(
    "A second reality check alongside the ATR ladder in Section 2: how far the option market's "
    "implied volatility says price could move by expiration."
)
default_iv = st.session_state.get("atm_iv", 20.0)
atm_iv_pct = st.number_input(
    "ATM implied volatility (%)",
    min_value=0.1,
    max_value=300.0,
    value=default_iv,
    step=0.5,
    help="Auto-filled from the live chain fetch in Section 3 if you loaded one there; otherwise enter it manually.",
)
years_for_em = dte / 365
expected_move = price * (atm_iv_pct / 100) * math.sqrt(years_for_em)
em_atr_mult = expected_move / atr if atr else None

col_em1, col_em2 = st.columns(2)
col_em1.metric("Expected move (1 SD, to expiration)", f"±${expected_move:.2f}")
col_em2.metric("Expected move in ATR multiples", f"{em_atr_mult:.2f}x" if em_atr_mult is not None else "—")
st.caption(
    "If this is much wider than your ATR-based distance in Section 2, the option market is pricing in "
    "more risk than the chart alone suggests — worth leaning further OTM per the Flex Rule."
)

# ---------------------------------------------------------------------------
# 5. Credit & profit target
# ---------------------------------------------------------------------------
st.header("5. Credit & Profit Target")
col7, col8 = st.columns(2)
with col7:
    credit = st.number_input("Credit received ($ per spread)", min_value=0.0, value=1.00, step=0.01, format="%.2f")
with col8:
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
