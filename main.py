
from AlgorithmImports import *
from collections import deque
from math import sqrt
import random


class AEGISAdaptiveMultiAsset(QCAlgorithm):

    def initialize(self):

        # ==========================================
        # 1. PORTFOLIO CONFIGURATION
        # ==========================================

        self.set_start_date(2022, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(100000)
        self.set_benchmark("SPY")

        self.max_equities = 15
        self.max_single_weight = 0.08
        self.max_total_exposure = 0.80

        self.crypto_budget = 0.15
        self.fx_budget = 0.10

        self.max_drawdown = 0.15
        self.target_volatility = 0.12

        # ==========================================
        # 2. DATA STRUCTURES
        # ==========================================

        self.equity_symbols = set()
        self.crypto_symbols = []
        self.fx_symbols = []

        self.indicators = {}

        self.arms = [
            "momentum",
            "mean_reversion",
            "trend"
        ]

        self.rewards = {
            arm: deque(maxlen=40)
            for arm in self.arms
        }

        self.counts = {
            arm: 0
            for arm in self.arms
        }

        self.active_arm = "momentum"
        self.pending_arm = None

        self.epsilon = 0.10
        self.rng = random.Random(17)

        # ==========================================
        # 3. PORTFOLIO RISK TRACKING
        # ==========================================

        self.previous_value = None

        self.peak_value = self.portfolio.total_portfolio_value

        self.risk_brake = False

        self.daily_returns = deque(maxlen=252)

        # ==========================================
        # 4. DYNAMIC EQUITY UNIVERSE
        # ==========================================

        self.universe_settings.resolution = Resolution.DAILY

        self.add_universe(self.coarse_selection)

        # ==========================================
        # 5. CRYPTOCURRENCY ASSETS
        # ==========================================

        for ticker in ["BTCUSDT", "ETHUSDT"]:

            symbol = self.add_crypto(
                ticker,
                Resolution.DAILY,
                Market.BINANCE
            ).symbol

            self.crypto_symbols.append(symbol)

            self.register_symbol(symbol)

        # ==========================================
        # 6. FOREX ASSETS
        # ==========================================

        for ticker in ["EURUSD", "GBPUSD", "USDJPY"]:

            symbol = self.add_forex(
                ticker,
                Resolution.DAILY,
                Market.OANDA
            ).symbol

            self.fx_symbols.append(symbol)

            self.register_symbol(symbol)

        # ==========================================
        # 7. BENCHMARK
        # ==========================================

        self.spy = self.add_equity(
            "SPY",
            Resolution.DAILY
        ).symbol

        self.register_symbol(self.spy)

        # ==========================================
        # 8. WEEKLY REBALANCING
        # ==========================================

        self.schedule.on(
            self.date_rules.week_start(self.spy),
            self.time_rules.after_market_open(self.spy, 30),
            self.rebalance
        )

        # ==========================================
        # 9. WARMUP
        # ==========================================

        self.set_warm_up(70, Resolution.DAILY)

        # ==========================================
        # 10. PERFORMANCE CHARTS
        # ==========================================

        self.add_chart(Chart("AEGIS Portfolio"))
        self.add_chart(Chart("AEGIS Risk"))
        self.add_chart(Chart("AEGIS Learning"))

        self.debug("AEGIS initialized successfully.")

    # ==============================================
    # 11. EQUITY UNIVERSE SELECTION
    # ==============================================

    def coarse_selection(self, coarse):

        candidates = [
            c for c in coarse
            if c.has_fundamental_data
            and c.price is not None
            and c.price > 5
            and c.dollar_volume is not None
            and c.dollar_volume > 5000000
        ]

        candidates.sort(
            key=lambda x: x.dollar_volume,
            reverse=True
        )

        return [
            c.symbol
            for c in candidates[:self.max_equities]
        ]

    # ==============================================
    # 12. SECURITY ADDITION AND REMOVAL
    # ==============================================

    def on_securities_changed(self, changes):

        for security in changes.added_securities:

            symbol = security.symbol

            if symbol.security_type == SecurityType.EQUITY:

                self.equity_symbols.add(symbol)

            self.register_symbol(symbol)

        for security in changes.removed_securities:

            self.equity_symbols.discard(
                security.symbol
            )

    # ==============================================
    # 13. INDICATOR REGISTRATION
    # ==============================================

    def register_symbol(self, symbol):

        if symbol in self.indicators:
            return

        self.indicators[symbol] = {

            "fast": self.ema(
                symbol,
                12,
                Resolution.DAILY
            ),

            "slow": self.ema(
                symbol,
                26,
                Resolution.DAILY
            ),

            "rsi": self.rsi(
                symbol,
                14,
                MovingAverageType.WILDERS,
                Resolution.DAILY
            ),

            "atr": self.atr(
                symbol,
                14,
                MovingAverageType.WILDERS,
                Resolution.DAILY
            ),

            "macd": self.macd(
                symbol,
                12,
                26,
                9,
                MovingAverageType.EXPONENTIAL,
                Resolution.DAILY
            ),

            "bb": self.bb(
                symbol,
                20,
                2,
                MovingAverageType.SIMPLE,
                Resolution.DAILY
            )
        }

    # ==============================================
    # 14. MAIN DATA EVENT
    # ==============================================

    def on_data(self, data):

        if self.is_warming_up:
            return

        portfolio_value = float(
            self.portfolio.total_portfolio_value
        )

        # Calculate realized portfolio return

        if (
            self.previous_value is not None
            and self.previous_value > 0
        ):

            daily_return = (
                portfolio_value / self.previous_value
            ) - 1

            self.daily_returns.append(daily_return)

            # Attribute reward to the previously selected arm.
            if self.pending_arm is not None:

                self.rewards[
                    self.pending_arm
                ].append(daily_return)

                self.counts[
                    self.pending_arm
                ] += 1

        self.previous_value = portfolio_value

        # ==========================================
        # 15. DRAWDOWN MONITORING
        # ==========================================

        self.peak_value = max(
            self.peak_value,
            portfolio_value
        )

        drawdown = (
            1 - portfolio_value / self.peak_value
            if self.peak_value > 0
            else 0
        )

        if drawdown >= self.max_drawdown:

            self.risk_brake = True

        # ==========================================
        # 16. CHARTING
        # ==========================================

        self.plot(
            "AEGIS Portfolio",
            "Portfolio Value",
            portfolio_value
        )

        self.plot(
            "AEGIS Risk",
            "Drawdown",
            drawdown
        )

        self.plot(
            "AEGIS Learning",
            "Selected Strategy",
            self.arms.index(self.active_arm)
        )

        # ==========================================
        # 17. RISK BRAKE
        # ==========================================

        if self.risk_brake:

            if self.portfolio.invested:

                self.liquidate()

            return

    # ==============================================
    # 18. ADAPTIVE STRATEGY SELECTION
    # ==============================================

    def choose_arm(self):

        # Exploration

        if self.rng.random() < self.epsilon:

            return self.rng.choice(self.arms)

        # Exploitation

        total = max(
            1,
            sum(self.counts.values())
        )

        scores = {}

        for arm in self.arms:

            rewards = self.rewards[arm]

            mean_reward = (
                sum(rewards) / len(rewards)
                if rewards
                else 0
            )

            exploration_bonus = sqrt(
                2 * (total + 1) /
                (self.counts[arm] + 1)
            )

            scores[arm] = (
                mean_reward
                + 0.0005 * exploration_bonus
            )

        return max(
            scores,
            key=scores.get
        )

    # ==============================================
    # 19. FEATURE ENGINEERING
    # ==============================================

    def features(self, symbol):

        if symbol not in self.indicators:
            return None

        ind = self.indicators[symbol]

        if not all(
            indicator.is_ready
            for indicator in ind.values()
        ):

            return None

        price = float(
            self.securities[symbol].price
        )

        atr = float(
            ind["atr"].current.value
        )

        middle = float(
            ind["bb"].middle_band.current.value
        )

        if price <= 0 or atr <= 0 or middle <= 0:
            return None

        return {

            "price": price,

            "fast": float(
                ind["fast"].current.value
            ),

            "slow": float(
                ind["slow"].current.value
            ),

            "rsi": float(
                ind["rsi"].current.value
            ),

            "atr_pct": atr / price,

            "macd": float(
                ind["macd"].current.value
            ),

            "macd_signal": float(
                ind["macd"].signal.current.value
            ),

            "lower": float(
                ind["bb"].lower_band.current.value
            )
        }

    # ==============================================
    # 20. ALPHA GENERATION
    # ==============================================

    def signal(self, f):

        if f is None:
            return 0.0

        # Momentum strategy

        if self.active_arm == "momentum":

            score = 0.0

            if f["macd"] > f["macd_signal"]:
                score += 0.50

            if f["rsi"] > 50:
                score += 0.25

            if f["price"] > f["fast"]:
                score += 0.25

            return score if score >= 0.50 else 0.0

        # Mean reversion strategy

        if self.active_arm == "mean_reversion":

            if (
                f["rsi"] < 30
                and f["price"] < f["lower"]
                and f["fast"] >= f["slow"]
            ):

                return 1.0

            return 0.0

        # Trend following strategy

        if self.active_arm == "trend":

            if (
                f["fast"] > f["slow"]
                and f["macd"] > f["macd_signal"]
            ):

                return 1.0

            return 0.0

        return 0.0

    # ==============================================
    # 21. PORTFOLIO REBALANCING
    # ==============================================

    def rebalance(self):

        if self.is_warming_up or self.risk_brake:
            return

        # Select strategy

        self.active_arm = self.choose_arm()

        self.pending_arm = self.active_arm

        candidates = []

        symbols = (
            list(self.equity_symbols)
            + self.crypto_symbols
            + self.fx_symbols
        )

        # ==========================================
        # 22. GENERATE ASSET SIGNALS
        # ==========================================

        for symbol in set(symbols):

            if symbol not in self.securities:
                continue

            security = self.securities[symbol]

            if (
                not security.is_tradable
                or security.price <= 0
            ):

                continue

            f = self.features(symbol)

            score = self.signal(f)

            if score <= 0 or f is None:
                continue

            # Volatility-adjusted position sizing

            annual_volatility = max(
                f["atr_pct"] * sqrt(252),
                0.05
            )

            raw_weight = min(
                self.max_single_weight,
                self.target_volatility
                / annual_volatility * 0.04
            )

            candidates.append(
                (symbol, score, raw_weight)
            )

        # ==========================================
        # 23. ASSET CLASS ALLOCATION
        # ==========================================

        equity_candidates = [
            x for x in candidates
            if x[0].security_type == SecurityType.EQUITY
            and x[0] != self.spy
        ]

        crypto_candidates = [
            x for x in candidates
            if x[0].security_type == SecurityType.CRYPTO
        ]

        forex_candidates = [
            x for x in candidates
            if x[0].security_type == SecurityType.FOREX
        ]

        targets = {}

        self.allocate(
            equity_candidates,
            0.55,
            targets
        )

        self.allocate(
            crypto_candidates,
            self.crypto_budget,
            targets
        )

        self.allocate(
            forex_candidates,
            self.fx_budget,
            targets
        )

        # ==========================================
        # 24. GROSS EXPOSURE CONTROL
        # ==========================================

        gross_exposure = sum(
            abs(weight)
            for weight in targets.values()
        )

        if gross_exposure > self.max_total_exposure:

            scale = (
                self.max_total_exposure
                / gross_exposure
            )

            targets = {
                symbol: weight * scale
                for symbol, weight in targets.items()
            }

        # ==========================================
        # 25. REMOVE UNQUALIFIED POSITIONS
        # ==========================================

        for holding in self.portfolio:

            symbol = holding.key

            if (
                holding.value.invested
                and symbol not in targets
            ):

                self.liquidate(symbol)

        # ==========================================
        # 26. EXECUTE PORTFOLIO TARGETS
        # ==========================================

        for symbol, weight in targets.items():

            self.set_holdings(
                symbol,
                weight,
                False
            )

        self.debug(
            "AEGIS | Strategy={} | Candidates={} | Positions={}".format(
                self.active_arm,
                len(candidates),
                len(targets)
            )
        )

    # ==============================================
    # 27. CAPITAL ALLOCATION ENGINE
    # ==============================================

    def allocate(
        self,
        sleeve,
        budget,
        targets
    ):

        if not sleeve:
            return

        denominator = sum(
            score * raw_weight
            for _, score, raw_weight in sleeve
        )

        if denominator <= 0:
            return

        for symbol, score, raw_weight in sleeve:

            weight = (
                budget
                * score
                * raw_weight
                / denominator
            )

            targets[symbol] = min(
                self.max_single_weight,
                weight
            )

    # ==============================================
    # 28. FINAL PERFORMANCE REPORT
    # ==============================================

    def on_end_of_algorithm(self):

        self.debug(
            "FINAL PORTFOLIO VALUE: {}".format(
                self.portfolio.total_portfolio_value
            )
        )

        self.debug(
            "STRATEGY SELECTION COUNTS: {}".format(
                self.counts
            )
        )

        self.debug(
            "STRATEGY MEAN REWARDS: {}".format({

                arm: (
                    sum(self.rewards[arm])
                    / len(self.rewards[arm])
                    if self.rewards[arm]
                    else None
                )

                for arm in self.arms
            })
        )
