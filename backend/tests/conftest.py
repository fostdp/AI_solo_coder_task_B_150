import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app.models.schemas import JansenParameters


@pytest.fixture
def default_params():
    return JansenParameters()


@pytest.fixture
def heavy_params():
    return JansenParameters(
        crank_length=150.0,
        rocker_length=250.0,
        coupler_length=300.0,
        ground_link=200.0,
        crank_speed=30.0,
        payload_mass=300.0,
        friction_coefficient=0.6,
        foot_radius=15.0,
    )


@pytest.fixture
def extreme_params():
    return JansenParameters(
        crank_length=300.0,
        rocker_length=500.0,
        coupler_length=600.0,
        ground_link=400.0,
        crank_speed=120.0,
        payload_mass=500.0,
        friction_coefficient=0.1,
        foot_radius=5.0,
    )


@pytest.fixture
def flat_terrain():
    return {'terrain_type': 'flat', 'slope': 0.0, 'roughness': 5.0, 'obstacle_density': 0.0, 'friction': 0.7}


@pytest.fixture
def rocky_terrain():
    return {'terrain_type': 'rocky', 'slope': 5.0, 'roughness': 60.0, 'obstacle_density': 0.6, 'friction': 0.5}


@pytest.fixture
def steep_terrain():
    return {'terrain_type': 'steep_slope', 'slope': 20.0, 'roughness': 15.0, 'obstacle_density': 0.15, 'friction': 0.6}
