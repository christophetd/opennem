""" Interval and time period definitions """
import logging

from opennem.core.loader import load_data
from opennem.schema.time import TimeInterval, TimePeriod

logger = logging.getLogger(__name__)


def load_intervals() -> list[TimeInterval]:
    interval_dicts = load_data("intervals.json")

    intervals = [TimeInterval(**i) for i in interval_dicts]

    return intervals


def load_periods() -> list[TimePeriod]:
    period_dicts = load_data("periods.json")

    periods = [TimePeriod(**i) for i in period_dicts]

    return periods


INTERVALS = load_intervals()

INTERVALS_SUPPORTED = [i.interval_human for i in INTERVALS]

PERIODS = load_periods()

PERIODS_SUPPORTED = [i.period_human for i in PERIODS]


def get_interval_by_size(interval_size: int) -> TimeInterval:
    """
    Get an interval by size

    """
    interval_lookup = list(filter(lambda x: x.interval == interval_size, INTERVALS))

    if interval_lookup:
        return interval_lookup.pop()

    raise Exception(f"Invalid interval {interval_size} not mapped")


def get_interval(interval_human: str) -> TimeInterval:
    interval_lookup = list(filter(lambda x: x.interval_human == interval_human, INTERVALS))

    if interval_lookup:
        return interval_lookup.pop()

    raise Exception(f"Invalid interval {interval_human} not mapped")


def get_period(period_human: str) -> TimePeriod:
    period_lookup = list(filter(lambda x: x.period_human == period_human, PERIODS))

    if period_lookup:
        return period_lookup.pop()

    raise Exception(f"Invalid interval {period_human} not mapped")
