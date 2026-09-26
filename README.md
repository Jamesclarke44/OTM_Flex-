# 📈 OTM Flex

**Stay Out of the Money. Stay Flexible. Collect Premium.**

OTM Flex is a rules-based credit spread trading system designed to generate consistent option income through disciplined trend-following and flexible strike selection.

The core philosophy is simple:

> When in doubt, go further OTM.

---

# Features

✅ Bull Put / Bear Call determination

✅ EMA20 trend analysis

✅ Delta-based strike selection

✅ ATR distance evaluation

✅ OTM Flex scoring system

✅ Trade approval status

✅ iPhone-friendly Streamlit interface

---

# OTM Flex Rules

## Trend Rule

- Price above EMA20 → Bull Put Spread
- Price below EMA20 → Bear Call Spread

## Delta Rule

Target short strike delta:

0.10 – 0.18

## Flex Rule

If risk increases:

- Move further OTM
- Lower delta
- Increase distance

Do not automatically reject a trade.

## Distance Rule

Use ATR as a reality check.

- Strong trend → 1-2 ATR distance
- Normal trend → 2 ATR distance
- Weak/choppy trend → 2-3 ATR distance

## Profit Rule

Take profits around:

50% of max profit

---

# OTM Flex Score

The app calculates a score out of 100.

| Category | Weight |
|----------|----------|
| Trend | 40 |
| Delta | 30 |
| Credit | 20 |
| Distance | 10 |

### Rating Scale

- 90-100 = Excellent
- 80-89 = Good
- 70-79 = Acceptable
- Below 70 = Pass

---

# Installation

Create a virtual environment:

```bash
python -m venv .venv
```

Activate:

Windows:

```bash
.venv\Scripts\activate
```

Mac/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Run the App

```bash
streamlit run app.py
```

The browser will automatically open.

---

# Version 1

Current capabilities:

- Manual trade inputs
- OTM Flex scoring
- Trade approval engine
- ATR distance calculations
- Delta validation

---

# Future Versions

## Version 2

- Live stock data
- Automatic EMA20 calculation
- Automatic ATR calculation

## Version 3

- Option chain integration
- Recommended strike selection
- OTM Flex trade scanner

## Version 4

- Portfolio tracking
- Position sizing
- Trade journal
- Performance analytics

---

# OTM Flex Philosophy

Trend determines direction.

Distance determines safety.

Flexibility determines consistency.

---

## Motto

> Stay Out of the Money. Stay Flexible. Collect Premium.
