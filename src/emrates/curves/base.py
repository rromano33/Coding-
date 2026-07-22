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
    """Monotone cubic Hermite interpolation (Fritsch-Carlson / PCHIP-style) of
    R(t) = -ln(DF) on the curve's own tau axis.

    Plain log-linear interpolation of discount factors is equivalent to a
    forward rate that's *constant within each pillar-to-pillar segment* and
    jumps at every pillar. Extracting a forward rate over a short window
    that starts mid-segment and ends mid-segment far from the valuation
    date (e.g. a Copom meeting ~1 year out, DI1 pillars a month apart)
    amplifies that jump by roughly t_start/(t_end-t_start) — a few bps of
    kink in the zero curve becomes tens of bps of spurious noise in the
    meeting-dated forward. That's real, reproducible noise, not signal
    (confirmed against Bloomberg's own CDIE screen, which uses a smoothed
    curve for exactly this reason, not raw last-traded futures prices).

    A first attempt at fixing this used an unconstrained quadratic forward
    per segment (in the style of Hagan-West's construction, without their
    case-by-case monotonicity clamps) — but without those clamps, an
    unconstrained quadratic can overshoot *more* than plain log-linear
    whenever the discrete segment forwards zigzag even slightly, which real
    market DI1 prints do. Monotone cubic Hermite fixes that by construction:
    each pillar's node derivative (= instantaneous forward there) is the
    harmonic mean of its two neighboring segments' average forwards, which
    is mathematically guaranteed to never exceed either of them — so the
    interpolated forward can't spike beyond what the two adjacent segments
    already imply. Where two adjacent segments slope in opposite directions
    (a real local peak/trough in the curve), the node derivative is zero,
    which is the correct, non-oscillating behavior there.
    """

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
        self._build_forward_nodes()

    def tau(self, start: date, end: date) -> float:
        return year_fraction(start, end, self.convention, self.calendar)

    def _signed_tau(self, start: date, end: date) -> float:
        """Like tau(), but allows end < start (returns a negative fraction) — needed
        to interpolate/extrapolate for dates before a pillar's start, e.g. a rolled
        curve valuing a swap that began before the new valuation date."""
        if end >= start:
            return self.tau(start, end)
        return -self.tau(end, start)

    def _build_forward_nodes(self) -> None:
        n = len(self.pillar_dates)
        t = [0.0] + [self.tau(self.valuation_date, d) for d in self.pillar_dates]
        R = [0.0] + [-math.log(df) for df in self.discount_factors]

        f = [0.0] * (n + 1)  # f[i]: average/secant forward over segment i=1..n; f[0] unused
        for i in range(1, n + 1):
            dt = t[i] - t[i - 1]
            f[i] = (R[i] - R[i - 1]) / dt if dt > 0 else 0.0

        d_node = [0.0] * (n + 1)  # node derivative (instantaneous forward) at each pillar, i=0..n
        if n == 1:
            d_node[0] = d_node[1] = f[1]
        else:
            d_node[0] = f[1]
            d_node[n] = f[n]
            for i in range(1, n):
                left, right = f[i], f[i + 1]
                if left == 0.0 or right == 0.0 or (left > 0) != (right > 0):
                    d_node[i] = 0.0  # opposite-signed neighboring slopes: a real local peak/trough
                else:
                    d_node[i] = 2.0 / (1.0 / left + 1.0 / right)  # harmonic mean, monotonicity-safe

        self._t, self._R, self._f, self._d_node, self._n = t, R, f, d_node, n

    def _segment_for(self, t_query: float) -> int:
        """Pillar segment i (1..n, spanning [t[i-1], t[i]]) covering t_query,
        extrapolating flat-segment beyond the first/last pillar."""
        t, n = self._t, self._n
        if t_query <= t[1]:
            return 1
        if t_query >= t[n - 1]:
            return n
        return next(i for i in range(2, n) if t[i - 1] <= t_query <= t[i])

    def _cumulative_rate(self, t_query: float) -> float:
        i = self._segment_for(t_query)
        t, R, d_node = self._t, self._R, self._d_node
        seg_len = t[i] - t[i - 1]
        x = (t_query - t[i - 1]) / seg_len if seg_len > 0 else 0.0

        # Standard cubic Hermite spline: matches R and its derivative (the
        # instantaneous forward) at both ends of the segment. R at the
        # pillars is reproduced exactly since h00(0)=h01(1)=1 and the other
        # two basis functions vanish there.
        h00 = 2 * x**3 - 3 * x**2 + 1
        h10 = x**3 - 2 * x**2 + x
        h01 = -2 * x**3 + 3 * x**2
        h11 = x**3 - x**2
        return h00 * R[i - 1] + h10 * seg_len * d_node[i - 1] + h01 * R[i] + h11 * seg_len * d_node[i]

    def discount_factor(self, d: date) -> float:
        if d == self.valuation_date:
            return 1.0
        t_query = self._signed_tau(self.valuation_date, d)
        return math.exp(-self._cumulative_rate(t_query))

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


def _bootstrap_coupon_pillars(
    valuation_date: date,
    pillars: list[Pillar],
    convention: DayCount,
    compounding: Compounding,
    coupon_frequency_months: int,
    calendar: Calendar | None,
    curve_dates: list[date],
    curve_dfs: list[float],
) -> None:
    """Solves each pillar's discount factor by a secant iteration rather than a
    single closed-form step: when a pillar spans more than one coupon period past
    the previously bootstrapped pillar, the intermediate coupon dates fall between
    the *candidate* new pillar and the last known one, so their interpolated
    discount factors depend on the very df being solved for. A one-shot closed
    form (using only prior pillars to interpolate those intermediate dates) is a
    few bps off; iterating against the trial curve that includes the candidate
    pillar removes that self-consistency error.

    curve_dates/curve_dfs are mutated in place, appending each bootstrapped
    pillar — pass them pre-seeded with any already-known pillars (e.g. a
    bullet short end bootstrapped separately) so the fixed-leg schedule's
    intermediate coupon dates can interpolate against those too.
    """

    def par_residual(p: Pillar, schedule: list[date], df_candidate: float) -> float:
        trial = DiscountCurve(
            valuation_date,
            curve_dates + [p.maturity],
            curve_dfs + [df_candidate],
            convention,
            compounding,
            calendar,
        )
        prior = [valuation_date] + schedule[:-1]
        fixed_leg = sum(trial.tau(a, b) * trial.discount_factor(b) for a, b in zip(prior, schedule))
        floating_leg = 1.0 - df_candidate
        return p.rate * fixed_leg - floating_leg

    for p in sorted(pillars, key=lambda p: p.maturity):
        schedule = generate_schedule(valuation_date, p.maturity, coupon_frequency_months, calendar)

        # closed-form estimate (exact when the pillar spans a single coupon
        # period past the last bootstrapped one) seeds the secant iteration
        prior_dates = schedule[:-1]
        taus = [
            year_fraction(prior_dates[i - 1] if i > 0 else valuation_date, prior_dates[i], convention, calendar)
            for i in range(len(prior_dates))
        ]
        last_known_df = curve_dfs[-1] if curve_dfs else 1.0
        s = sum(tau * last_known_df for tau in taus)  # crude seed, refined below
        tau_last = year_fraction(prior_dates[-1] if prior_dates else valuation_date, p.maturity, convention, calendar)
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

    def build(self, valuation_date: date, pillars: list[Pillar]) -> DiscountCurve:
        curve_dates: list[date] = []
        curve_dfs: list[float] = []
        _bootstrap_coupon_pillars(
            valuation_date, pillars, self.convention, self.compounding,
            self.coupon_frequency_months, self.calendar, curve_dates, curve_dfs,
        )
        return DiscountCurve(
            valuation_date, curve_dates, curve_dfs, self.convention, self.compounding, self.calendar
        )


class HybridCurveBuilder:
    """Bullet (zero-rate) pillars out to bullet_cutoff_months, then a
    periodic-coupon par-swap bootstrap beyond it — Chile (SPC) and Colombia
    (IBR) both trade bullet out to 18 months, then switch to a periodic-
    coupon swap for 2Y+ (confirmed via Bloomberg DES — CHSWP5: SemiAnnual
    both legs; CLSWIB5: Quarterly both legs, float leg resets daily/
    compounded but pays quarterly — 22/07/2026)."""

    def __init__(
        self,
        convention: DayCount,
        compounding: Compounding,
        coupon_frequency_months: int,
        bullet_cutoff_months: int,
        calendar: Calendar | None = None,
    ):
        self.convention = convention
        self.compounding = compounding
        self.coupon_frequency_months = coupon_frequency_months
        self.bullet_cutoff_months = bullet_cutoff_months
        self.calendar = calendar

    def _cutoff_date(self, valuation_date: date) -> date:
        total = valuation_date.month - 1 + self.bullet_cutoff_months
        year = valuation_date.year + total // 12
        month = total % 12 + 1
        day = min(valuation_date.day, 28)
        return date(year, month, day)

    def build(self, valuation_date: date, pillars: list[Pillar]) -> DiscountCurve:
        cutoff = self._cutoff_date(valuation_date)
        bullet_pillars = [p for p in pillars if p.maturity <= cutoff]
        coupon_pillars = [p for p in pillars if p.maturity > cutoff]

        curve_dates: list[date] = []
        curve_dfs: list[float] = []
        for p in sorted(bullet_pillars, key=lambda p: p.maturity):
            tau = year_fraction(valuation_date, p.maturity, self.convention, self.calendar)
            curve_dates.append(p.maturity)
            curve_dfs.append(discount_factor(p.rate, tau, self.compounding))

        _bootstrap_coupon_pillars(
            valuation_date, coupon_pillars, self.convention, self.compounding,
            self.coupon_frequency_months, self.calendar, curve_dates, curve_dfs,
        )

        return DiscountCurve(
            valuation_date, curve_dates, curve_dfs, self.convention, self.compounding, self.calendar
        )
