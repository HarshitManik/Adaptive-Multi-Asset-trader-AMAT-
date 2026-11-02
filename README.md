# daptive Multi-Asset Quantitative Trading Strategy

AEGIS is a QuantConnect LEAN research project exploring a rules-based, long-only portfolio across US equities, cryptocurrency, and major FX pairs. It combines technical-indicator signals, volatility-aware position sizing, asset-class allocation limits, and an epsilon-greedy strategy-selection experiment.

> **Research disclaimer:** This repository contains experimental backtesting code. The historical backtest is not evidence of a live-trading edge, a forecast of future returns, or investment advice.

## Backtest snapshot

**Period:** 1 January 2022 – 31 December 2025  
**Initial capital:** USD 100,000  
**Reported ending equity:** USD 135,588.28

| Metric | Reported result |
|---|---:|
| Total return | 35.59% |
| CAGR / compounding annual return | 7.898% |
| Maximum drawdown | 11.70% |
| Sharpe ratio | 0.212 |
| Sortino ratio | 0.262 |
| Win rate | 59% |
| Average winning trade | 0.33% |
| Average losing trade | -0.29% |
| Profit/loss ratio | 1.16 |
| Total orders | 730 |
| Fees | USD 448.15 |
| Beta | 0.173 |
| Alpha | 0.007 |
| PSR | 2.506% |

These values are transcribed from the QuantConnect screenshots in [`results/`](results/). They document the displayed run and have not been independently reproduced in this repository.

### Interpreting the results

The backtest shows a positive cumulative return, but the **0.212 Sharpe ratio is weak** and the **2.506% Probabilistic Sharpe Ratio (PSR)** does not provide persuasive evidence that the measured Sharpe is statistically robust. The cumulative return should not be interpreted in isolation. Out-of-sample testing, benchmark comparison, realistic trading costs, and robustness checks are still required.

## Strategy architecture

### 1. Universe

- **US equities:** Dynamic coarse-fundamental universe. Securities must have fundamental data, price above USD 5, and dollar volume above USD 5 million. The 15 highest-dollar-volume candidates are selected.
- **Crypto:** BTCUSDT and ETHUSDT on Binance.
- **FX:** EURUSD, GBPUSD, and USDJPY on OANDA.
- **Benchmark:** SPY.
- Strategy securities use daily-resolution data in this version.

### 2. Indicators

Daily indicators registered for tracked symbols:

- EMA(12) and EMA(26)
- RSI(14), Wilder smoothing
- ATR(14), Wilder smoothing
- MACD(12, 26, 9), exponential moving averages
- Bollinger Bands(20, 2 standard deviations)

Signals are generated only after the indicators are ready.

### 3. Signal models

The algorithm selects one of three signal arms at each scheduled weekly rebalance.

**Momentum**
- MACD line above signal line: +0.50
- RSI above 50: +0.25
- Price above EMA(12): +0.25
- Requires a score of at least 0.50.

**Mean reversion**
- RSI below 30
- Price below the lower Bollinger Band
- EMA(12) at or above EMA(26)

**Trend following**
- EMA(12) above EMA(26)
- MACD line above signal line

The strategy is long-only.

### 4. Adaptive strategy selection

An epsilon-greedy multi-armed-bandit-style selector chooses between momentum, mean reversion, and trend:

- Exploration probability (`epsilon`): 10%
- Random seed: 17
- Reward history: rolling deque of up to 40 observations per arm
- Exploration selects an arm randomly; exploitation selects the arm with the highest mean reward plus an exploration bonus.

**Important limitation:** the reward assigned to an arm is the overall portfolio's daily return while that arm is marked as pending. It is not an isolated return stream for that strategy. Returns may reflect positions opened under earlier arms and other concurrent effects. The reward attribution is therefore approximate, not a rigorous comparison of the three strategies.

### 5. Position sizing and portfolio construction

- Volatility proxy: ATR / price, annualized using `sqrt(252)`.
- Raw position weight uses a 12% target-volatility parameter and is capped at 8%.
- Equity sleeve budget: 55%.
- Crypto sleeve budget: 15%.
- FX sleeve budget: 10%.
- Maximum single-position weight: 8%.
- Maximum gross exposure: 80%.

Within each sleeve, weights are allocated in proportion to signal score multiplied by raw weight, then capped at the single-position limit.

### 6. Portfolio risk control

The algorithm tracks portfolio value and its running peak. If peak-to-current drawdown reaches 15%, it activates a risk brake, liquidates invested holdings, and stops further rebalancing.

This V1 code has a portfolio-level drawdown brake. It does **not** implement individual 5% stop-losses, 5% take-profits, or trailing stops.

## Repository structure

```text
AEGIS-Adaptive-Multi-Asset/
├── main.py
├── README.md
├── .gitignore
├── LICENSE
└── results/
    ├── 01-quantconnect-code-editor.png
    ├── 02-backtest-overview.png
    ├── 03-backtest-charts.png
    └── 04-performance-statistics.png
```

## Run on QuantConnect

1. Create or open a Python project in QuantConnect LEAN.
2. Replace the project's `main.py` with this repository's `main.py`.
3. Confirm the required US equity, Binance crypto, and OANDA FX data are available in your QuantConnect environment.
4. Run a backtest using the same date range and initial capital.
5. Compare the new output with the committed screenshots. Results can differ because of data revisions, engine versions, data availability, or configuration changes.

This is QuantConnect LEAN algorithm code. It is not a standalone Python script; it depends on LEAN's `AlgorithmImports` and algorithm runtime.

## Known limitations and next research steps

1. **Bandit reward attribution:** portfolio returns are assigned to the currently pending arm rather than isolated arm-specific portfolios.
2. **Limited validation:** only one historical backtest window is documented. It does not establish out-of-sample performance or robustness across regimes.
3. **Execution realism:** there is no separately calibrated market-impact, spread, or slippage model.
4. **No trade-level protective orders:** V1 has a portfolio drawdown brake, not per-position stop-loss, take-profit, or trailing-stop logic.
5. **No correlation-aware optimizer:** weights use sleeve budgets and signal/volatility scores; there is no covariance-matrix optimizer.
6. **No futures or options:** this version covers equities, crypto, and FX.
7. **No order-book microstructure:** no order-book depth, bid/ask imbalance, CVD, or tick-level execution signals.
8. **Exposure caps are constraints, not an optimal diversification guarantee.**

Potential extensions: arm-specific shadow portfolios, walk-forward and regime-based evaluation, benchmark-relative attribution, realistic transaction-cost modelling, correlation-aware risk allocation, and stress testing.

## Reproducibility

For a stronger research record, retain the QuantConnect backtest ID, LEAN engine version, data configuration, brokerage model, fee model, and parameter changes with each new result snapshot.

## License

See [`LICENSE`](LICENSE). The MIT license is included as a permissive default; check third-party and platform terms before redistribution.
