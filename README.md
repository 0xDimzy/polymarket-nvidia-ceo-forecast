# Polymarket NVIDIA CEO forecaster

Entry for [make.fun/bounty/polymarket-nvidia-ceo-forecast-01](https://make.fun/bounty/polymarket-nvidia-ceo-forecast-01):
forecast the Yes price of every trading market of Polymarket's "Next CEO of
NVIDIA?" event at every minute of the 4 hours after each checkpoint, as five
quantiles (0.05, 0.25, 0.5, 0.75, 0.95).

## Model

`main.py` (Python 3.13, stdlib only, deterministic, offline) reads every
`*.in` case in `$MAKEFUN_INPUT_DIR` (default `/input`) and writes the
matching `*.out` to `$MAKEFUN_OUTPUT_DIR` (default `/output`).

- **Center — last price, shrunk to the cross-market sum.** The 24 Yes prices
  are mutually exclusive outcomes, so their sum should sit near 1. When it
  does not, the board is collectively mispriced and the next moves partly
  correct it: `center = x * (1 + 0.6 * (1 - S))`, where `S` is the sum of the
  markets' last prices. No trend extrapolation: the last price (after this
  shrink) is the median. Every drift and EWMA center tested was much worse.
- **Spread — per-market recent volatility.** `sigma_i` is the mean absolute
  1-minute move over the last 18 hours, winsorized at 0.05 (the raw standard
  deviation is dominated by rare huge jumps and is far too wide), floored at
  0.0002 and capped at 0.02. Quantiles widen like a random walk:
  `q_tau(h) = center + z_tau * mult_tau * sigma_i * sqrt(h)`, with Gaussian
  `z` and per-level multipliers `[1.0, 1.0, 1.0, 0.25, 1.0]`: the 75%
  quantile sits much closer to the median than Gaussian (prices usually sit
  still or tick down a little; the far tails are jump-driven).

## Results (local scoring on the six public practice cases)

| model | pinball loss | median error | 90% coverage |
| --- | --- | --- | --- |
| house baseline (persistence, sigma 0.0025) | 0.363589 | 0.767503 | 0.9496 |
| this entry | **0.256209** | 0.752803 | 0.8646 |

Per-case loss: p00 0.3841, p01 0.2961, p02 0.3424, p03 0.2488, p04 0.2074,
p05 0.1110. Runs in ~0.05 s per case (limit 8 s), output is deterministic
byte-for-byte across runs.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
