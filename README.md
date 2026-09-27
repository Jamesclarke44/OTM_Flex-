OTM Flex™ — Credit Spread Strike Selection Engine

A manual-first Streamlit calculator for selecting and evaluating credit spread strikes using the OTM Flex™ framework:

Trend → Delta → Distance → Flex

The app is designed to help structure a credit-spread decision without turning every uncertain market condition into an automatic “no trade.”

⸻

Features

Trend

The app determines the initial direction from EMA20:

* Price > EMA20 → Bull Put Spread
* Price < EMA20 → Bear Call Spread

EMA20, EMA50 and EMA200 are also used to describe trend strength.

⸻

Momentum

The app displays:

* RSI
* MACD line
* MACD signal
* EMA alignment

These produce a Strong / Average / Choppy-Uncertain context score.

Momentum does not automatically reject a trade.

⸻

Delta

The primary short-strike target is:

0.10–0.18 delta

The app can calculate an estimated Black-Scholes delta from the Yahoo Finance option chain.

The delta calculation can also be overridden manually.

⸻

Distance

ATR is used as a reality check.

OTM Flex guidelines:

Trend	ATR distance
Strong	1–2 ATR
Average	Around 2 ATR
Choppy / uncertain	2–3 ATR

Distance is treated as a major part of risk management.

⸻

Flex Ladder

The app identifies a starting strike and then displays progressively further-OTM strikes.

Example:

650 → 645 → 640 → 635

If the original strike feels too close:

Move further OTM.

The app does not automatically cancel the trade simply because the market is choppy or volatility is elevated.

⸻

Expected Move

The app calculates a volatility-based expected move:

Expected Move =
Price × IV × √(DTE / 365)

This is displayed alongside ATR so the user can compare:

* Strike distance
* ATR
* Implied expected move

The expected move is a reference, not a guarantee.

⸻

Earnings

The app attempts to retrieve the next earnings date from Yahoo Finance.

If earnings fall inside the selected expiration window, the app displays a warning.

Always verify the earnings date with your broker before entering a trade.

⸻

Credit

The app calculates:

* Credit received
* Maximum loss
* 50% profit target
* Return on risk

For example:

$5.00 wide spread
$1.00 credit
Maximum profit = $1.00
Maximum loss = $4.00
50% profit target = $0.50

⸻

Position Sizing

The position-sizing calculator uses:

Risk Budget =
Account Size × Risk %

Then:

Maximum Contracts =
Risk Budget ÷ Maximum Loss Per Contract

For standard U.S. ETF options, one contract normally represents 100 shares.

Example:

$20,000 account
2% risk
= $400 risk budget
$5-wide spread
$1.00 credit
= $400 maximum loss per contract
Maximum contracts = 1

The app also displays several risk levels for comparison.

These are calculations, not recommended position sizes.

⸻

Files

The project contains three files:

otm-flex/
│
├── app.py
├── requirements.txt
└── README.md

⸻

Installation

1. Install Python

Use Python 3.10 or newer.

Check your version:

python --version

or:

python3 --version

⸻

2. Install the required packages

From the project folder:

pip install -r requirements.txt

If your computer uses python3:

pip3 install -r requirements.txt

⸻

Run the Streamlit App

From the same folder:

streamlit run app.py

Streamlit should open the application in your browser.

If it doesn’t, Streamlit will display a local address similar to:

http://localhost:8501

Open that address in your browser.

⸻

Using the App

Step 1 — Enter the ticker

Example:

SPY

Then select:

Fetch Price & Indicators

The app attempts to retrieve:

* Current price
* EMA20
* EMA50
* EMA200
* RSI
* MACD
* ATR
* Approximate earnings date

All of these remain manually editable.

⸻

Step 2 — Confirm direction

The basic OTM Flex direction is:

Price > EMA20
        ↓
Bull Put Spread

or:

Price < EMA20
        ↓
Bear Call Spread

⸻

Step 3 — Check trend context

Review:

* EMA stack
* RSI
* MACD

The app categorizes the environment as:

Strong
Average
Choppy / Uncertain

This is context rather than an automatic trade blocker.

⸻

Step 4 — Check ATR

Determine the approximate distance from the current price.

For example:

SPY = $650
ATR = $5

Then:

1 ATR = $5
2 ATR = $10
3 ATR = $15

For a Bull Put:

1 ATR → $645
2 ATR → $640
3 ATR → $635

For a Bear Call:

1 ATR → $655
2 ATR → $660
3 ATR → $665

Actual strikes are rounded according to the selected strike increment.

⸻

Step 5 — Load the Option Chain

Select:

Load Expirations

Then select an expiration and:

Fetch Option Chain

The app calculates an estimated delta using:

* Current price
* Strike
* Implied volatility
* Risk-free rate
* DTE

The target zone is:

0.10–0.18 delta

⸻

Step 6 — Apply Flex

The process is:

Trend
   ↓
Find 0.10–0.18 delta
   ↓
Check ATR distance
   ↓
Check expected move
   ↓
Check credit
   ↓
Check liquidity
   ↓
If uncomfortable:
move further OTM

The Flex ladder allows you to compare multiple strikes rather than automatically abandoning the setup.

⸻

Step 7 — Check Expiration

The typical OTM Flex range is:

7–45 DTE

The app also checks the approximate earnings date.

If earnings fall inside the expiration period, review the position before proceeding.

⸻

Step 8 — Check Credit

Enter:

* Credit received
* Spread width
* Minimum acceptable credit

The calculator determines:

Maximum profit
Maximum loss
50% profit target
Return on risk

For example:

$5 spread
$0.80 credit
Maximum profit:
$80 per contract
Maximum loss:
$420 per contract
50% profit target:
$40

⸻

Step 9 — Position Size

Enter:

Account size
Risk per trade %

The calculator determines the corresponding risk budget and maximum number of contracts based on the spread’s maximum loss.

Remember:

Maximum loss =
(Spread Width − Credit) × 100

for a standard 100-share option contract.

⸻

Step 10 — Manage the Trade

The OTM Flex profit-taking rule is approximately:

50% of maximum profit

If a position becomes threatened, review:

1. EMA20 trend
2. Short-strike delta
3. Distance from price
4. ATR
5. Expected move
6. Volatility
7. Time remaining

Possible actions include:

* Closing
* Reducing risk
* Moving further OTM
* Rolling if the new position still makes sense

The app does not automatically execute trades or recommend a roll.

⸻

Important Data Notes

Yahoo Finance

The free Yahoo Finance connection is useful for research and screening, but it should not be treated as a real-time broker feed.

Option quotes may be delayed or incomplete.

Always verify:

* Bid
* Ask
* Last price
* Open interest
* Volume
* Implied volatility
* Earnings
* Expiration

with your broker before placing an order.

⸻

Black-Scholes Delta

The calculated delta is an estimate.

Actual broker-provided option Greeks may differ because of:

* Volatility surface
* Interest rates
* Dividends
* Pricing models
* Market conditions
* Data timing

For ETF options, the dividend yield can also affect theoretical delta.

The app therefore allows manual adjustment.

⸻

No Trade Execution

OTM Flex is a calculator and decision-support tool.

It does not:

* Place trades
* Connect to your brokerage account
* Automatically sell options
* Automatically roll positions
* Guarantee probability of profit
* Guarantee that a strike will remain OTM

⸻

OTM Flex Core Philosophy

The system is intentionally simple:

TREND
  ↓
DIRECTION
  ↓
DELTA
  ↓
DISTANCE
  ↓
ATR
  ↓
FLEX
  ↓
CREDIT
  ↓
RISK

The defining rule is:

When in doubt, go further OTM — not out of the trade.

And the motto:

Stay out of the money. Stay flexible. Collect premium.

⸻

Troubleshooting

Yahoo Finance doesn’t return data

Try:

SPY
QQQ
IWM
VOO
DIA

If one ticker doesn’t work, check whether Yahoo Finance recognizes the symbol.

⸻

Option chain doesn’t load

Yahoo Finance can temporarily rate-limit requests.

Try:

1. Wait a few minutes.
2. Refresh the app.
3. Try another ticker.
4. Enter the option data manually.

The app is intentionally designed to continue working with manual inputs.

⸻

Streamlit doesn’t start

Try:

python -m streamlit run app.py

instead of:

streamlit run app.py

⸻

Running From GitHub / Streamlit Community Cloud

Upload:

app.py
requirements.txt
README.md

to a GitHub repository.

When creating a Streamlit deployment, select:

Main file:
app.py

Streamlit will use:

requirements.txt

to install:

* Streamlit
* pandas
* yfinance

No API key is required for the Yahoo Finance data used by this version.

⸻

Project Goal

OTM Flex is intended to make the credit-spread process repeatable:

Trend determines direction.

Delta finds the starting strike.

Distance provides the primary risk buffer.

ATR provides a reality check.

Flex provides another OTM choice when the first strike feels too close.

Credit and position sizing determine whether the spread fits the trade plan.
