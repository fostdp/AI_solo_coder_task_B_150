from app.vehicle_comparator import (
    VehicleComparator,
    WHEELBARROW_PARAMS,
    CARRIAGE_PARAMS,
    TERRAIN_PROFILES,
    HISTORICAL_SOURCES,
    compare_obstacle_clearing,
    compare_on_terrain,
    get_transport_profiles,
    get_historical_sources,
    generate_radar_data,
)

TransportComparisonAnalyzer = VehicleComparator

__all__ = [
    'TransportComparisonAnalyzer',
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
