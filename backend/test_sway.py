import sys
sys.path.insert(0, '.')
from app.analysis.cargo_stability import CargoStabilityAnalyzer
from app.models.schemas import JansenParameters

params = JansenParameters()
analyzer = CargoStabilityAnalyzer(params)

# Test 1: verify sway_amplitude=0 is identical to original behavior
result_no_sway = analyzer._evaluate_stability_over_gait(0, 0, 150)
result_zero_sway = analyzer._evaluate_stability_over_gait(0, 0, 150, sway_amplitude=0)
print('Test 1 - backward compat (sway=0 same as no sway):')
print('  min_margin equal:', result_no_sway['min_stability_margin'] == result_zero_sway['min_stability_margin'])
print('  sway fields present:', 'sway_amplitude_used' in result_zero_sway)
assert result_no_sway['min_stability_margin'] == result_zero_sway['min_stability_margin']
assert 'sway_amplitude_used' not in result_zero_sway

# Test 2: sway_amplitude > 0 returns extra fields
result_sway = analyzer._evaluate_stability_over_gait(0, 0, 150, sway_amplitude=50)
print('Test 2 - sway > 0 adds fields:')
print('  sway_amplitude_used:', result_sway.get('sway_amplitude_used'))
print('  worst_case_position:', result_sway.get('worst_case_position'))
print('  stability_reduction_percent:', result_sway.get('stability_reduction_percent'))
print('  is_stable:', result_sway['is_stable'])
assert 'sway_amplitude_used' in result_sway
assert 'worst_case_position' in result_sway
assert 'stability_reduction_percent' in result_sway

# Test 3: _evaluate_with_sway
sway_result = analyzer._evaluate_with_sway(0, 0, 150, sway_amplitude=50, sway_directions=8)
print('Test 3 - _evaluate_with_sway:')
print('  positions evaluated:', len(sway_result['all_positions']))
print('  min_margin:', sway_result['min_margin'])
print('  avg_margin:', sway_result['avg_margin'])
assert len(sway_result['all_positions']) == 9  # 8 directions + center
assert 'worst_case_position' in sway_result

# Test 4: analyze_sway_sensitivity
sens = analyzer.analyze_sway_sensitivity(max_sway=50, num_steps=5)
print('Test 4 - analyze_sway_sensitivity:')
print('  num steps:', len(sens['sway_analysis']))
print('  has worst_direction:', all('worst_direction' in r for r in sens['sway_analysis']))
print('  critical_sway:', sens['critical_sway_amplitude'])
assert len(sens['sway_analysis']) == 5
assert all('sway_amplitude' in r for r in sens['sway_analysis'])
assert all('min_margin' in r for r in sens['sway_analysis'])
assert all('is_stable' in r for r in sens['sway_analysis'])

# Test 5: analyze_cargo_sway_grid
grid = analyzer.analyze_cargo_sway_grid(mass_steps=3, sway_steps=3, mass_range=(0, 200), sway_range=(0, 50))
print('Test 5 - analyze_cargo_sway_grid:')
print('  grid size:', len(grid['grid']))
print('  contour rows:', len(grid['contour_data']))
print('  stability_ratio:', grid['stability_ratio'])
assert len(grid['grid']) == 9
assert len(grid['contour_data']) == 3
assert 'stability_ratio' in grid
assert 'masses' in grid
assert 'sway_amplitudes' in grid

# Test 6: existing methods with sway_amplitude
result = analyzer.analyze_cargo_position_grid(payload_mass=150, grid_resolution=3, sway_amplitude=20)
print('Test 6 - analyze_cargo_position_grid with sway:')
print('  has sway_amplitude_used:', 'sway_amplitude_used' in result)
print('  first cell has worst_case:', 'worst_case_position' in result['grid'][0])
assert 'sway_amplitude_used' in result
assert 'worst_case_position' in result['grid'][0]

result2 = analyzer.find_optimal_cargo_position(payload_mass=150, sway_amplitude=20)
print('Test 7 - find_optimal_cargo_position with sway:')
print('  has sway_amplitude_used:', 'sway_amplitude_used' in result2)
print('  has worst_case_position:', 'worst_case_position' in result2)
assert 'sway_amplitude_used' in result2
assert 'worst_case_position' in result2

result3 = analyzer.analyze_height_effect(num_steps=3, sway_amplitude=20)
print('Test 8 - analyze_height_effect with sway:')
print('  has sway_amplitude_used:', 'sway_amplitude_used' in result3)
assert 'sway_amplitude_used' in result3

result4 = analyzer.analyze_mass_effect(num_steps=3, sway_amplitude=20)
print('Test 9 - analyze_mass_effect with sway:')
print('  has sway_amplitude_used:', 'sway_amplitude_used' in result4)
assert 'sway_amplitude_used' in result4

# Test 10: verify that sway reduces stability (min_margin with sway <= min_margin without sway)
print('Test 10 - sway reduces stability margin:')
nominal = analyzer._evaluate_stability_over_gait(100, 50, 200, sway_amplitude=0)
with_sway = analyzer._evaluate_stability_over_gait(100, 50, 200, sway_amplitude=50)
print('  nominal min_margin:', nominal['min_stability_margin'])
print('  with sway min_margin:', with_sway['min_stability_margin'])
print('  sway <= nominal:', with_sway['min_stability_margin'] <= nominal['min_stability_margin'])
assert with_sway['min_stability_margin'] <= nominal['min_stability_margin'] + 1e-9

print()
print('All tests passed!')
