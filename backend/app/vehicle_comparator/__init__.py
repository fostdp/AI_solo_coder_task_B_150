from app.vehicle_comparator.core import VehicleComparator
from app.vehicle_comparator.historical_params import (
    WHEELBARROW_PARAMS,
    CARRIAGE_PARAMS,
    TERRAIN_PROFILES,
    HISTORICAL_SOURCES,
)


def compare_obstacle_clearing(terrain_data):
    comparator = VehicleComparator()
    return comparator.compare_obstacle_clearing(terrain_data)


def compare_on_terrain(terrain_type):
    comparator = VehicleComparator()
    return comparator.compare_on_terrain(terrain_type)


def get_transport_profiles():
    comparator = VehicleComparator()
    return comparator.get_transport_profiles()


def get_historical_sources():
    comparator = VehicleComparator()
    return comparator.get_historical_sources()


def generate_radar_data(terrain_type):
    comparator = VehicleComparator()
    return comparator.generate_radar_data(terrain_type)


__all__ = [
    'VehicleComparator',
    'WHEELBARROW_PARAMS',
    'CARRIAGE_PARAMS',
    'TERRAIN_PROFILES',
    'HISTORICAL_SOURCES',
    'compare_obstacle_clearing',
    'compare_on_terrain',
    'get_transport_profiles',
    'get_historical_sources',
    'generate_radar_data',
]
