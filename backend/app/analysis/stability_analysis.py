import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy import signal
from datetime import datetime

from app.models.schemas import JansenParameters, Point3D, Point2D, SensorData
from app.simulation.multibody_dynamics import MultibodyDynamics
from app.simulation.jansen_linkage import JansenLinkageSolver


class StabilityAnalyzer:
    def __init__(self, params: JansenParameters):
        self.params = params
        self.dynamics = MultibodyDynamics(params)
        self.linkage_solver = JansenLinkageSolver(params)
        
        self.stability_thresholds = {
            'excellent': 50.0,
            'good': 30.0,
            'marginal': 10.0,
            'poor': 0.0
        }

    def analyze_static_stability(
        self,
        crank_angle: float,
        body_inclination: float = 0.0,
        num_legs: int = 4
    ) -> Dict:
        joints = self.linkage_solver.solve_linkage(crank_angle)
        com_positions = self.dynamics.calculate_link_centers_of_mass(joints)
        total_com = self.dynamics.calculate_total_center_of_mass(com_positions, body_inclination)
        forces = self.dynamics.calculate_joint_forces(joints, com_positions, body_inclination)
        zmp = self.dynamics.calculate_zero_moment_point(total_com, forces, joints, body_inclination)
        support_polygon = self.dynamics.calculate_support_polygon(joints, num_legs)
        stability_margin = self.dynamics.calculate_stability_margin(zmp, support_polygon)
        
        stability_level = self._classify_stability(stability_margin)
        
        return {
            'center_of_mass': {
                'x': total_com.x,
                'y': total_com.y,
                'z': total_com.z
            },
            'zero_moment_point': {
                'x': zmp.x,
                'y': zmp.y
            },
            'support_polygon': [{'x': p.x, 'y': p.y} for p in support_polygon],
            'stability_margin': float(stability_margin),
            'stability_level': stability_level,
            'is_stable': stability_margin > 0,
            'body_inclination': body_inclination,
            'crank_angle': crank_angle
        }

    def analyze_dynamic_stability(
        self,
        sensor_history: List[SensorData],
        window_size: int = 10
    ) -> Dict:
        if len(sensor_history) < window_size:
            return {'error': 'Insufficient data for dynamic analysis'}
        
        inclinations = [s.body_inclination for s in sensor_history]
        crank_angles = [s.crank_angle for s in sensor_history]
        timestamps = [s.timestamp.timestamp() for s in sensor_history]
        
        inclination_variance = np.var(inclinations)
        inclination_rate = np.gradient(inclinations, timestamps)
        
        max_inclination_rate = np.max(np.abs(inclination_rate))
        
        energy = self._calculate_dynamic_energy(sensor_history)
        
        tipping_risk = self._assess_tipping_risk(
            np.mean(inclinations),
            max_inclination_rate,
            inclination_variance
        )
        
        frequency_analysis = self._analyze_vibration_frequencies(
            inclinations,
            np.mean(np.diff(timestamps))
        )
        
        stability_derivatives = self._calculate_stability_derivatives(
            sensor_history,
            crank_angles
        )
        
        return {
            'inclination_stats': {
                'mean': float(np.mean(inclinations)),
                'variance': float(inclination_variance),
                'max_rate': float(max_inclination_rate)
            },
            'tipping_risk': tipping_risk,
            'dynamic_energy': energy,
            'frequency_analysis': frequency_analysis,
            'stability_derivatives': stability_derivatives,
            'overall_dynamic_stability': self._calculate_overall_dynamic_stability(
                inclination_variance,
                max_inclination_rate,
                tipping_risk
            )
        }

    def _classify_stability(self, stability_margin: float) -> str:
        if stability_margin >= self.stability_thresholds['excellent']:
            return 'excellent'
        elif stability_margin >= self.stability_thresholds['good']:
            return 'good'
        elif stability_margin >= self.stability_thresholds['marginal']:
            return 'marginal'
        elif stability_margin >= self.stability_thresholds['poor']:
            return 'poor'
        else:
            return 'unstable'

    def _calculate_dynamic_energy(self, sensor_history: List[SensorData]) -> Dict:
        displacements = [s.leg_displacement for s in sensor_history]
        timestamps = [s.timestamp.timestamp() for s in sensor_history]
        
        velocities = np.gradient(displacements, timestamps)
        accelerations = np.gradient(velocities, timestamps)
        
        total_mass = sum(self.dynamics.mass_properties.values())
        
        kinetic_energy = 0.5 * total_mass * np.mean(velocities**2)
        potential_energy = total_mass * self.dynamics.gravity * np.mean([s.ground_elevation for s in sensor_history])
        
        return {
            'kinetic_energy': float(kinetic_energy),
            'potential_energy': float(potential_energy),
            'total_energy': float(kinetic_energy + potential_energy),
            'energy_variation': float(np.std(kinetic_energy + potential_energy))
        }

    def _assess_tipping_risk(
        self,
        avg_inclination: float,
        max_rate: float,
        variance: float
    ) -> Dict:
        inclination_threshold = 15.0
        rate_threshold = 5.0
        variance_threshold = 10.0
        
        inclination_score = np.clip(abs(avg_inclination) / inclination_threshold, 0, 1)
        rate_score = np.clip(max_rate / rate_threshold, 0, 1)
        variance_score = np.clip(variance / variance_threshold, 0, 1)
        
        overall_risk = (inclination_score * 0.5 + rate_score * 0.3 + variance_score * 0.2) * 100
        
        risk_level = 'LOW'
        if overall_risk > 75:
            risk_level = 'CRITICAL'
        elif overall_risk > 50:
            risk_level = 'HIGH'
        elif overall_risk > 25:
            risk_level = 'MEDIUM'
        
        return {
            'overall_risk_score': float(overall_risk),
            'risk_level': risk_level,
            'inclination_score': float(inclination_score * 100),
            'rate_score': float(rate_score * 100),
            'variance_score': float(variance_score * 100)
        }

    def _analyze_vibration_frequencies(
        self,
        data: List[float],
        sampling_interval: float
    ) -> Dict:
        if sampling_interval <= 0:
            sampling_interval = 1.0
        
        n = len(data)
        freqs = np.fft.fftfreq(n, sampling_interval)
        fft = np.fft.fft(data)
        power_spectrum = np.abs(fft)**2
        
        positive_freqs = freqs[:n//2]
        positive_power = power_spectrum[:n//2]
        
        dominant_freq_idx = np.argmax(positive_power)
        dominant_frequency = positive_freqs[dominant_freq_idx]
        
        main_frequencies = []
        sorted_indices = np.argsort(positive_power)[-5:][::-1]
        for idx in sorted_indices:
            if positive_power[idx] > 0.1 * positive_power[dominant_freq_idx]:
                main_frequencies.append({
                    'frequency': float(positive_freqs[idx]),
                    'power': float(positive_power[idx])
                })
        
        return {
            'dominant_frequency': float(dominant_frequency),
            'main_frequencies': main_frequencies,
            'sampling_frequency': float(1.0 / sampling_interval),
            'total_power': float(np.sum(positive_power))
        }

    def _calculate_stability_derivatives(
        self,
        sensor_history: List[SensorData],
        crank_angles: List[float]
    ) -> Dict:
        stability_margins = []
        
        for i, sensor in enumerate(sensor_history):
            result = self.analyze_static_stability(
                crank_angles[i] % 360,
                sensor.body_inclination
            )
            stability_margins.append(result['stability_margin'])
        
        if len(stability_margins) < 2:
            return {'error': 'Insufficient data'}
        
        margins_array = np.array(stability_margins)
        timestamps = np.array([s.timestamp.timestamp() for s in sensor_history])
        
        d_stability = np.gradient(margins_array, timestamps)
        d2_stability = np.gradient(d_stability, timestamps)
        
        stability_trend = 'stable'
        if np.mean(d_stability) > 1.0:
            stability_trend = 'improving'
        elif np.mean(d_stability) < -1.0:
            stability_trend = 'deteriorating'
        
        return {
            'stability_margins': [float(m) for m in stability_margins],
            'first_derivative': [float(d) for d in d_stability],
            'second_derivative': [float(d) for d in d2_stability],
            'stability_trend': stability_trend,
            'rate_of_change': float(np.mean(d_stability)),
            'acceleration': float(np.mean(d2_stability))
        }

    def _calculate_overall_dynamic_stability(
        self,
        variance: float,
        max_rate: float,
        tipping_risk: Dict
    ) -> float:
        variance_score = 1.0 - np.clip(variance / 20.0, 0, 1)
        rate_score = 1.0 - np.clip(max_rate / 10.0, 0, 1)
        risk_score = 1.0 - tipping_risk['overall_risk_score'] / 100.0
        
        overall = (variance_score * 0.3 + rate_score * 0.3 + risk_score * 0.4) * 100
        
        return float(max(0, min(100, overall)))

    def calculate_critical_inclination(
        self,
        crank_angle: float,
        direction: str = 'pitch'
    ) -> float:
        joints = self.linkage_solver.solve_linkage(crank_angle)
        support_polygon = self.dynamics.calculate_support_polygon(joints)
        
        min_x = min(p.x for p in support_polygon)
        max_x = max(p.x for p in support_polygon)
        
        com_positions = self.dynamics.calculate_link_centers_of_mass(joints)
        total_com = self.dynamics.calculate_total_center_of_mass(com_positions, 0.0)
        
        height = total_com.y
        
        if direction == 'pitch':
            margin = min(total_com.x - min_x, max_x - total_com.x)
        else:
            margin = min(total_com.z - min(p.y for p in support_polygon),
                        max(p.y for p in support_polygon) - total_com.z)
        
        critical_angle = np.degrees(np.arctan2(margin, height))
        
        return float(critical_angle * 0.8)

    def predict_stability_evolution(
        self,
        current_inclination: float,
        target_inclination: float,
        duration: float,
        crank_speed: float
    ) -> Dict:
        num_steps = 100
        inclinations = np.linspace(current_inclination, target_inclination, num_steps)
        times = np.linspace(0, duration, num_steps)
        
        stability_scores = []
        critical_angles = []
        
        for i, incl in enumerate(inclinations):
            crank_angle = (crank_speed * times[i]) % 360
            result = self.analyze_static_stability(crank_angle, incl)
            stability_scores.append(result['stability_margin'])
            critical_angles.append(self.calculate_critical_inclination(crank_angle))
        
        min_stability = min(stability_scores)
        stability_violation = any(s < 0 for s in stability_scores)
        
        feasibility = True
        if stability_violation:
            feasibility = False
        elif min_stability < 10:
            feasibility = False
        
        return {
            'time_points': times.tolist(),
            'inclination_profile': inclinations.tolist(),
            'stability_scores': [float(s) for s in stability_scores],
            'critical_angles': [float(a) for a in critical_angles],
            'min_stability': float(min_stability),
            'feasible': feasibility,
            'recommended_speed': float(crank_speed * 0.8 if min_stability < 30 else crank_speed)
        }

    def compute_stability_ellipsoid(
        self,
        crank_angle: float
    ) -> Dict:
        num_samples = 50
        roll_angles = np.linspace(-20, 20, num_samples)
        pitch_angles = np.linspace(-20, 20, num_samples)
        
        stability_map = np.zeros((num_samples, num_samples))
        
        for i, roll in enumerate(roll_angles):
            for j, pitch in enumerate(pitch_angles):
                total_inclination = np.sqrt(roll**2 + pitch**2)
                result = self.analyze_static_stability(crank_angle, total_inclination)
                stability_map[i, j] = result['stability_margin']
        
        stable_region = stability_map > 0
        
        return {
            'roll_range': [-20.0, 20.0],
            'pitch_range': [-20.0, 20.0],
            'stability_map': stability_map.tolist(),
            'stable_region': stable_region.tolist(),
            'max_safe_roll': float(np.max(np.abs(roll_angles[np.any(stable_region, axis=1)]))) if np.any(stable_region) else 0.0,
            'max_safe_pitch': float(np.max(np.abs(pitch_angles[np.any(stable_region, axis=0)]))) if np.any(stable_region) else 0.0
        }
