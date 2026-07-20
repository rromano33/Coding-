"""Generic discount-curve engine, shared by every country.

Two pillar styles cover all eight countries:

- ZeroRateCurveBuilder: for instruments that are economically a single
  zero-coupon rate to maturity — Brazil's DI futures (BUS/252,
  exponential) and bullet OIS-style swaps with no interim coupon
  (Chile Cámara, Colombia IBR). No bootstrap iteration is needed: each
  pillar's discount factor only depends on its own rate and tenor.

- ParSwapCurveBuilder: for par swaps with periodic fixed-leg coupons
  (Mexico TIIE, South Africa JIBAR, Poland WIBOR, Czech PRIBOR, Hungary
  BUBOR). Requires sequential bootstrap: each pillar's discount factor is
  solved (secant iteration, see build()) against the discount factors
  already bootstrapped for earlier coupon dates.

Which builder applies to which country is a config choice
(config/countries/<country>.yaml -> pillar_type), not a code branch —
see reports/priced_bc.py or scripts/run_daily_pricing.py for the factory
that reads that config and picks the right builder.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from emrates.conventions.compounding import Compounding, discount_factor, forward_rate, zero_rate
from emrates.conventions.daycount import DayCount, year_fraction
from emrates.conventions.schedule import generate_schedule
from emrates.data.calendars import Calendar


@dataclass(frozen=True)
class Pillar:
    maturity: date
    rate: float  # quoted par/zero rate, as a decimal (0.1075, not 10.75)


class DiscountCurve:
    """Log-linear interpolation on discount factors (piecewise-constant forward rates)."""

    def __init__(
        self,
        valuation_date: date,
        pillar_dates: list[date],
        discount_factors: list[float],
        convention: DayCount,
        compounding: Compounding,
        calendar: Calendar | None,
    ):
        if pillar_dates != sorted(pillar_dates):
            raise ValueError("pillar_dates must be sorted ascending")
        self.valuation_date = valuation_date
        self.pillar_dates = pillar_dates
        self.discount_factors = discount_factors
        self.convention = convention
        self.compounding = compounding
        self.calendar = calendar

    def tau(self, start: date, end: date) -> float:
        return year_fraction(start, end, self.convention, self.calendar)

    def discount_factor(self, d: date) -> float:
        if d == self.valuation_date:
            return 1.0
        dates, dfs = self.pillar_dates, self.discount_factors
        if d <= dates[0]:
            t0, t1 = self.valuation_date, dates[0]
            df0, df1 = 1.0, dfs[0]
        elif d >= dates[-1]:
            if len(dates) == 1:
                t0, t1, df0, df1 = self.valuation_date, dates[0], 1.0, dfs[0]
            else:
                t0, t1, df0, df1 = dates[-2], dates[-1], dfs[-2], dfs[-1]
        else:
            i = next(k for k in range(len(dates) - 1) if dates[k] <= d <= dates[k + 1])
            t0, t1, df0, df1 = dates[i], dates[i + 1], dfs[i], dfs[i + 1]

        if t0 == t1:
            return df1
        frac = (d - t0).days / (t1 - t0).days
        log_df = math.log(df0) + frac * (math.log(df1) - math.log(df0))
        return math.exp(log_df)

    def zero_rate(self, d: date) -> float:
        tau = self.tau(self.valuation_date, d)
        return zero_rate(self.discount_factor(d), tau, self.compounding)

    def forward_rate(self, start: date, end: date) -> float:
        tau = self.tau(start, end)
        return forward_rate(self.discount_factor(start), self.discount_factor(end), tau, self.compounding)


class ZeroRateCurveBuilder:
    def __init__(self, convention: DayCount, compounding: Compounding, calendar: Calendar | None = None):
        self.convention = convention
        self.compounding = compounding
        self.calendar = calendar

    def build(self, valuation_date: date, pillars: list[Pillar]) -> DiscountCurve:
        pillars = sorted(pillars, key=lambda p: p.maturity)
        dfs = []
        for p in pillars:
            tau = year_fraction(valuation_date, p.maturity, self.convention, self.calendar)
            dfs.append(discount_factor(p.rate, tau, self.compounding))
        return DiscountCurve(
            valuation_date, [p.maturity for p in pillars], dfs, self.convention, self.compounding, self.calendar
        )


class ParSwapCurveBuilder:
    """Bootstraps a par-swap curve with periodic fixed-leg coupons.

    coupon_frequency_months: e.g. 3 for quarterly JIBAR/WIBOR/PRIBOR/BUBOR swaps,
    or the relevant tenor in months for TIIE (28-day swaps are handled as a
    28-calendar-day-ish approx via coupon_frequency_months; if that's not precise
    enough for TIIE once conventions are confirmed, generate the schedule in
    calendar days instead of months here).
    """

    def __init__(
        self,
        convention: DayCount,
        compounding: Compounding,
        coupon_frequency_months: int,
        calendar: Calendar | None = None,
    ):
        self.convention = convention
        self.compounding = compounding
        self.coupon_frequency_months = coupon_frequency_months
        self.calendar = calendar

    def _schedule(self, valuation_date: date, maturity: date) -> list[date]:
        return generate_schedule(valuation_date, maturity, self.coupon_frequency_months, self.calendar)

    def build(self, valuation_date: date, pillars: list[Pillar]) -> DiscountCurve:
        """Solves each pillar's discount factor by a secant iteration rather than a
        single closed-form step: when a pillar spans more than one coupon period past
        the previously bootstrapped pillar, the intermediate coupon dates fall between
        the *candidate* new pillar and the last known one, so their interpolated
        discount factors depend on the very df being solved for. A one-shot closed
        form (using only prior pillars to interpolate those intermediate dates) is a
        few bps off; iterating against the trial curve that includes the candidate
        pillar removes that self-consistency error.
        """
        pillars = sorted(pillars, key=lambda p: p.maturity)
        curve_dates: list[date] = []
        curve_dfs: list[float] = []

        def par_residual(p: Pillar, schedule: list[date], df_candidate: float) -> float:
            trial = DiscountCurve(
                valuation_date,
                curve_dates + [p.maturity],
                curve_dfs + [df_candidate],
                self.convention,
                self.compounding,
                self.calendar,
            )
            prior = [valuation_date] + schedule[:-1]
            fixed_leg = sum(trial.tau(a, b) * trial.discount_factor(b) for a, b in zip(prior, schedule))
            floating_leg = 1.0 - df_candidate
            return p.rate * fixed_leg - floating_leg

        for p in pillars:
            schedule = self._schedule(valuation_date, p.maturity)

            # closed-form estimate (exact when the pillar spans a single coupon
            # period past the last bootstrapped one) seeds the secant iteration
            prior_dates = schedule[:-1]
            taus = [
                year_fraction(
                    prior_dates[i - 1] if i > 0 else valuation_date, prior_dates[i], self.convention, self.calendar
                )
                for i in range(len(prior_dates))
            ]
            last_known_df = curve_dfs[-1] if curve_dfs else 1.0
            s = sum(tau * last_known_df for tau in taus)  # crude seed, refined below
            tau_last = year_fraction(
                prior_dates[-1] if prior_dates else valuation_date, p.maturity, self.convention, self.calendar
            )
            df0 = (1.0 - p.rate * s) / (1.0 + p.rate * tau_last)
            df1 = df0 * 1.0001

            f0, f1 = par_residual(p, schedule, df0), par_residual(p, schedule, df1)
            for _ in range(50):
                if f1 == f0:
                    break
                df_next = df1 - f1 * (df1 - df0) / (f1 - f0)
                df0, f0 = df1, f1
                df1 = df_next
                f1 = par_residual(p, schedule, df1)
                if abs(f1) < 1e-14:
                    break

            curve_dates.append(p.maturity)
            curve_dfs.append(df1)

        return DiscountCurve(
            valuation_date, curve_dates, curve_dfs, self.convention, self.compounding, self.calendar
        )
