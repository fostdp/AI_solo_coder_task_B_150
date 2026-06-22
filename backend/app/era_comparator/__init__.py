from app.era_comparator.core import EraComparator
from app.era_comparator.robot_specs import (
    STATIC_METRICS,
    STANDARD_SOURCES,
    ERAS,
)


def compare_all_metrics(params=None):
    comparator = EraComparator()
    return comparator.compare_all_metrics(params)


def generate_era_radar(params=None):
    comparator = EraComparator()
    return comparator.generate_era_radar(params)


def generate_timeline():
    comparator = EraComparator()
    return comparator.generate_timeline()


def compare_mechanism_principle(params=None):
    comparator = EraComparator()
    return comparator.compare_mechanism_principle(params)


def get_standard_sources():
    comparator = EraComparator()
    return comparator.get_standard_sources()


__all__ = [
    'EraComparator',
    'STATIC_METRICS',
    'STANDARD_SOURCES',
    'ERAS',
    'compare_all_metrics',
    'generate_era_radar',
    'generate_timeline',
    'compare_mechanism_principle',
    'get_standard_sources',
]
