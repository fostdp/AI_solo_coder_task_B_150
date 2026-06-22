import numpy as np


def generate_sway_positions(
    cargo_x: float,
    cargo_z: float,
    sway_amplitude: float,
    sway_directions: int = 8,
) -> list:
    if sway_amplitude <= 0:
        return [{'x': cargo_x, 'z': cargo_z}]

    direction_angles = np.linspace(0, 2 * np.pi, sway_directions, endpoint=False)
    positions = [{'x': cargo_x, 'z': cargo_z}]

    for angle in direction_angles:
        dx = sway_amplitude * np.cos(angle)
        dz = sway_amplitude * np.sin(angle)
        positions.append({'x': cargo_x + dx, 'z': cargo_z + dz})

    return positions


def get_worst_direction(
    cargo_x: float,
    cargo_z: float,
    worst_pos: dict,
) -> str:
    dx = worst_pos['x'] - cargo_x
    dz = worst_pos['z'] - cargo_z

    if abs(dx) < 1e-9 and abs(dz) < 1e-9:
        return 'center'

    angle = np.arctan2(dz, dx)
    angle_deg = float(np.degrees(angle)) % 360

    direction_names = [
        (0, 'east'),
        (45, 'northeast'),
        (90, 'north'),
        (135, 'northwest'),
        (180, 'west'),
        (225, 'southwest'),
        (270, 'south'),
        (315, 'southeast'),
    ]

    closest_dir = 'east'
    min_diff = 360
    for target_angle, name in direction_names:
        diff = abs(angle_deg - target_angle)
        if diff > 180:
            diff = 360 - diff
        if diff < min_diff:
            min_diff = diff
            closest_dir = name

    return closest_dir


def compute_sway_results(
    positions: list,
    evaluate_func,
) -> dict:
    all_results = []
    min_margin = float('inf')
    avg_margin = 0.0
    worst_position = {'x': positions[0]['x'], 'z': positions[0]['z']}

    for pos in positions:
        result = evaluate_func(pos['x'], pos['z'])
        pos_min = result['min_stability_margin']
        all_results.append({
            'x': pos['x'],
            'z': pos['z'],
            'min_margin': pos_min,
            'avg_margin': result['avg_stability_margin'],
        })
        avg_margin += pos_min
        if pos_min < min_margin:
            min_margin = pos_min
            worst_position = {'x': pos['x'], 'z': pos['z']}

    avg_margin /= len(all_results) if all_results else 1

    return {
        'min_margin': float(min_margin),
        'avg_margin': float(avg_margin),
        'worst_case_position': worst_position,
        'all_positions': all_results,
    }


def find_critical_value(results: list, value_key: str, stable_key: str = 'is_stable'):
    for i in range(len(results) - 1):
        if results[i][stable_key] and not results[i + 1][stable_key]:
            return (results[i][value_key] + results[i + 1][value_key]) / 2
    return None
