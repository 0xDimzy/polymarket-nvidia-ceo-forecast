#!/usr/bin/env python3
"""Forecast Polymarket's "Next CEO of NVIDIA?" Yes prices, 4 hours ahead, minute by minute.

Model (fitted on the six public practice cases; practice pinball loss 0.2562 vs the
house baseline's 0.3636):

- Center: each market's last price, shrunk toward the cross-market sum-to-one
  constraint. The 24 Yes prices are mutually exclusive outcomes, so their sum
  should sit near 1; when it does not, the board is collectively mispriced and
  the next moves partly correct it: center = x * (1 + 0.6 * (1 - S)), where S
  is the sum of the markets' last prices. No trend extrapolation: the last
  price (after this shrink) is the median; every drift/EWMA center tested
  was much worse.
- Spread: per-market volatility from the recent 18 hours of 1-minute moves,
  winsorized at 0.05 (the raw standard deviation is dominated by rare huge
  jumps and is far too wide). sigma_i = clamp(trimmean(|diff|, 18h), 0.0002,
  0.02). Quantiles widen like a random walk: q_tau(h) = center + z_tau *
  mult_tau * sigma_i * sqrt(h), with Gaussian z and per-level multipliers
  [1.0, 1.0, 1.0, 0.25, 1.0]: the 75% quantile sits much closer to the
  median than Gaussian (prices usually sit still or tick down a little;
  the far tails are jump-driven and symmetric-ish at 5%/95%).

Stdlib only, deterministic, no network. Reads every *.in in $MAKEFUN_INPUT_DIR
(default /input) and writes the matching *.out to $MAKEFUN_OUTPUT_DIR
(default /output).
"""

import json
import math
import os
from pathlib import Path

# Standard normal quantiles at the five scored levels, in order.
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]
# Per-level spread multipliers (tau = 0.05, 0.25, 0.5, 0.75, 0.95).
MULT = [1.0, 1.0, 1.0, 0.25, 1.0]
# Volatility window: last 18 hours of 1-minute prices.
VOL_WINDOW = 1080
# Winsor cap for single-minute moves when estimating volatility.
WINSOR_CAP = 0.05
# Floor / cap on the per-market sigma (price units per square-root minute).
SIGMA_FLOOR = 0.0002
SIGMA_CAP = 0.02
# Cross-market sum-to-one shrink strength.
SUM_SHRINK = 0.6


def clamp6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    v = round(min(1.0, max(0.0, x)) * 1e6) / 1e6
    return v + 0.0


def market_sigma(prices):
    """Robust per-market 1-minute move scale over the last VOL_WINDOW minutes."""
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    start = max(0, n - VOL_WINDOW - 1)
    total = 0.0
    count = 0
    for i in range(start, n - 1):
        d = prices[i + 1] - prices[i]
        if d < 0.0:
            d = -d
        if d > WINSOR_CAP:
            d = WINSOR_CAP
        total += d
        count += 1
    if count == 0:
        return SIGMA_FLOOR
    sig = total / count
    if sig < SIGMA_FLOOR:
        return SIGMA_FLOOR
    if sig > SIGMA_CAP:
        return SIGMA_CAP
    return sig


def forecast_market(prices, horizon, center):
    """240 rows of five quantiles around `center` for one market."""
    sig = market_sigma(prices)
    rows = []
    for h in range(1, horizon + 1):
        s = sig * math.sqrt(h)
        row = [clamp6(center + z * m * s) for z, m in zip(Z, MULT)]
        # Guard the non-decreasing invariant against any float edge.
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def market_center(prices, shrink):
    """Forecast center for one market: last price shrunk to the sum-to-one
    constraint. An (unexpected) empty history falls back to 0.5 so the run
    still produces a valid forecast instead of crashing the case."""
    if not prices:
        return 0.5
    return prices[-1] * shrink


def main():
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in input_dir.iterdir() if p.name.endswith(".in"))
    for path in inputs:
        case = json.loads(path.read_text(encoding="utf-8"))
        horizon = int(case["horizon_minutes"])
        markets = case["markets"]
        total = sum((m["prices"][-1] if m["prices"] else 0.5) for m in markets)
        shrink = 1.0 + SUM_SHRINK * (1.0 - total)
        forecasts = []
        for m in markets:
            prices = m["prices"]
            center = market_center(prices, shrink)
            forecasts.append({"id": m["id"], "q": forecast_market(prices, horizon, center)})
        out_path = output_dir / (path.stem + ".out")
        out_path.write_text(json.dumps({"forecasts": forecasts}) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
