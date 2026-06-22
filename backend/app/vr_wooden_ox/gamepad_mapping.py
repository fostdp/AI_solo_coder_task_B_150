import numpy as np


def apply_deadzone(value, deadzone=0.1):
    if abs(value) < deadzone:
        return 0.0
    sign = 1 if value > 0 else -1
    return sign * (abs(value) - deadzone) / (1 - deadzone)


def apply_response_curve(value, curve='quadratic'):
    if curve == 'linear':
        return value
    elif curve == 'quadratic':
        sign = 1 if value >= 0 else -1
        return sign * (value ** 2)
    elif curve == 'cubic':
        return value ** 3
    else:
        raise ValueError(f"Unknown curve type: {curve}. Use 'linear', 'quadratic', or 'cubic'.")


def apply_sensitivity(value, sensitivity=1.0):
    return value * sensitivity


def process_axis(raw_value, deadzone=0.1, curve='quadratic', sensitivity=1.0):
    value = apply_deadzone(raw_value, deadzone)
    value = apply_response_curve(value, curve)
    value = apply_sensitivity(value, sensitivity)
    return float(max(-1.0, min(1.0, value)))
