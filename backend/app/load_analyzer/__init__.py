from typing import Tuple

from app.load_analyzer.core import LoadAnalyzer
from app.models.schemas import JansenParameters


def _get_default_analyzer() -> LoadAnalyzer:
    return LoadAnalyzer(JansenParameters())


def analyze_cargo_position_grid(
    payload_mass,
    x_range,
    z_range,
    grid_resolution,
    body_inclination,
    sway_amplitude,
):
    analyzer = _get_default_analyzer()
    return analyzer.analyze_cargo_position_grid(
        payload_mass=payload_mass,
        x_range=x_range,
        z_range=z_range,
        grid_resolution=grid_resolution,
        body_inclination=body_inclination,
        sway_amplitude=sway_amplitude,
    )


def find_optimal_cargo_position(
    payload_mass,
    body_inclination,
    sway_amplitude,
):
    analyzer = _get_default_analyzer()
    return analyzer.find_optimal_cargo_position(
        payload_mass=payload_mass,
        body_inclination=body_inclination,
        sway_amplitude=sway_amplitude,
    )


def analyze_height_effect(
    payload_mass,
    cargo_x,
    cargo_z,
    height_range,
    num_steps,
    sway_amplitude,
):
    analyzer = _get_default_analyzer()
    return analyzer.analyze_height_effect(
        payload_mass=payload_mass,
        cargo_x=cargo_x,
        cargo_z=cargo_z,
        height_range=height_range,
        num_steps=num_steps,
        sway_amplitude=sway_amplitude,
    )


def analyze_mass_effect(
    cargo_x,
    cargo_z,
    mass_range,
    num_steps,
    body_inclination,
    sway_amplitude,
):
    analyzer = _get_default_analyzer()
    return analyzer.analyze_mass_effect(
        cargo_x=cargo_x,
        cargo_z=cargo_z,
        mass_range=mass_range,
        num_steps=num_steps,
        body_inclination=body_inclination,
        sway_amplitude=sway_amplitude,
    )


def analyze_sway_sensitivity(
    cargo_x,
    cargo_z,
    payload_mass,
    cargo_y,
    body_inclination,
    max_sway,
    num_steps,
):
    analyzer = _get_default_analyzer()
    return analyzer.analyze_sway_sensitivity(
        cargo_x=cargo_x,
        cargo_z=cargo_z,
        payload_mass=payload_mass,
        cargo_y=cargo_y,
        body_inclination=body_inclination,
        max_sway=max_sway,
        num_steps=num_steps,
    )


def analyze_cargo_sway_grid(
    cargo_x,
    cargo_z,
    cargo_y,
    body_inclination,
    mass_range,
    sway_range,
    mass_steps,
    sway_steps,
):
    analyzer = _get_default_analyzer()
    return analyzer.analyze_cargo_sway_grid(
        cargo_x=cargo_x,
        cargo_z=cargo_z,
        cargo_y=cargo_y,
        body_inclination=body_inclination,
        mass_range=mass_range,
        sway_range=sway_range,
        mass_steps=mass_steps,
        sway_steps=sway_steps,
    )


__all__ = [
    'LoadAnalyzer',
    'analyze_cargo_position_grid',
    'find_optimal_cargo_position',
    'analyze_height_effect',
    'analyze_mass_effect',
    'analyze_sway_sensitivity',
    'analyze_cargo_sway_grid',
]
