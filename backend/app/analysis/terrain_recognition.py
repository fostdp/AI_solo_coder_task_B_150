import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy import signal, interpolate
from scipy.ndimage import gaussian_filter

from app.models.schemas import TerrainData, TerrainPoint, Point2D


class TerrainRecognizer:
    def __init__(self):
        self.terrain_types = {
            'flat': {'max_slope': 5.0, 'roughness': 10.0},
            'gentle_slope': {'max_slope': 15.0, 'roughness': 20.0},
            'steep_slope': {'max_slope': 30.0, 'roughness': 30.0},
            'rough': {'max_slope': 10.0, 'roughness': 50.0},
            'obstacle_field': {'max_slope': 20.0, 'roughness': 80.0}
        }

    def analyze_terrain(self, terrain_data: TerrainData) -> Dict:
        elevation_grid = self._points_to_grid(terrain_data)
        
        slope_x, slope_y = np.gradient(elevation_grid, terrain_data.resolution)
        slope_magnitude = np.sqrt(slope_x**2 + slope_y**2)
        slope_degrees = np.degrees(np.arctan(slope_magnitude))
        
        roughness = self._calculate_roughness(elevation_grid)
        
        curvature = self._calculate_curvature(elevation_grid, terrain_data.resolution)
        
        obstacles = self._detect_obstacles(elevation_grid, terrain_data.resolution)
        
        terrain_type = self._classify_terrain(
            np.mean(slope_degrees),
            roughness,
            len(obstacles)
        )
        
        return {
            'terrain_type': terrain_type,
            'elevation_stats': {
                'min': float(np.min(elevation_grid)),
                'max': float(np.max(elevation_grid)),
                'mean': float(np.mean(elevation_grid)),
                'std': float(np.std(elevation_grid))
            },
            'slope_stats': {
                'min': float(np.min(slope_degrees)),
                'max': float(np.max(slope_degrees)),
                'mean': float(np.mean(slope_degrees)),
                'std': float(np.std(slope_degrees))
            },
            'roughness': float(roughness),
            'curvature_stats': {
                'min': float(np.min(curvature)),
                'max': float(np.max(curvature)),
                'mean': float(np.mean(curvature))
            },
            'obstacles': obstacles,
            'traversability_score': self._calculate_traversability_score(
                slope_degrees,
                roughness,
                obstacles
            ),
            'passable_regions': self._identify_passable_regions(
                slope_degrees,
                roughness,
                max_slope=20.0,
                max_roughness=50.0
            )
        }

    def _points_to_grid(self, terrain_data: TerrainData) -> np.ndarray:
        grid = np.zeros((terrain_data.grid_size, terrain_data.grid_size))
        
        points_dict = {}
        for point in terrain_data.points:
            x_idx = int(point.x / terrain_data.resolution)
            y_idx = int(point.y / terrain_data.resolution)
            if 0 <= x_idx < terrain_data.grid_size and 0 <= y_idx < terrain_data.grid_size:
                points_dict[(x_idx, y_idx)] = point.elevation
        
        for i in range(terrain_data.grid_size):
            for j in range(terrain_data.grid_size):
                if (i, j) in points_dict:
                    grid[i, j] = points_dict[(i, j)]
                else:
                    grid[i, j] = self._interpolate_elevation(
                        i, j, points_dict, terrain_data.resolution
                    )
        
        grid = gaussian_filter(grid, sigma=1)
        
        return grid

    def _interpolate_elevation(
        self,
        x: int,
        y: int,
        points_dict: Dict[Tuple[int, int], float],
        resolution: float
    ) -> float:
        if not points_dict:
            return 0.0
        
        distances = []
        elevations = []
        
        for (px, py), elev in points_dict.items():
            dist = np.sqrt((x - px)**2 + (y - py)**2) * resolution
            if dist < 5 * resolution:
                distances.append(dist)
                elevations.append(elev)
        
        if not distances:
            nearest = min(points_dict.keys(), key=lambda p: (p[0]-x)**2 + (p[1]-y)**2)
            return points_dict[nearest]
        
        weights = 1.0 / (np.array(distances) + 1e-6)
        weights /= np.sum(weights)
        
        return float(np.sum(np.array(elevations) * weights))

    def _calculate_roughness(self, elevation_grid: np.ndarray) -> float:
        mean_elev = np.mean(elevation_grid)
        deviations = elevation_grid - mean_elev
        roughness = np.sqrt(np.mean(deviations**2))
        
        laplacian = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]])
        texture = signal.convolve2d(elevation_grid, laplacian, mode='same')
        texture_roughness = np.mean(np.abs(texture))
        
        return float(roughness + texture_roughness * 0.1)

    def _calculate_curvature(
        self,
        elevation_grid: np.ndarray,
        resolution: float
    ) -> np.ndarray:
        dzdx = np.gradient(elevation_grid, resolution, axis=0)
        dzdy = np.gradient(elevation_grid, resolution, axis=1)
        d2zdx2 = np.gradient(dzdx, resolution, axis=0)
        d2zdy2 = np.gradient(dzdy, resolution, axis=1)
        d2zdxdy = np.gradient(dzdx, resolution, axis=1)
        
        curvature = (d2zdx2 * (1 + dzdy**2) - 2 * dzdx * dzdy * d2zdxdy + d2zdy2 * (1 + dzdx**2)) / \
                    (1 + dzdx**2 + dzdy**2)**(3/2)
        
        return curvature

    def _detect_obstacles(
        self,
        elevation_grid: np.ndarray,
        resolution: float,
        height_threshold: float = 50.0
    ) -> List[Dict]:
        obstacles = []
        
        mean_elev = np.mean(elevation_grid)
        threshold = mean_elev + height_threshold
        
        regions = []
        visited = np.zeros_like(elevation_grid, dtype=bool)
        
        for i in range(elevation_grid.shape[0]):
            for j in range(elevation_grid.shape[1]):
                if elevation_grid[i, j] > threshold and not visited[i, j]:
                    region = self._flood_fill(elevation_grid, i, j, threshold, visited)
                    if len(region) > 4:
                        regions.append(region)
        
        for idx, region in enumerate(regions):
            coords = np.array(region)
            x_coords = coords[:, 0] * resolution
            y_coords = coords[:, 1] * resolution
            heights = [elevation_grid[int(c[0]), int(c[1])] for c in coords]
            
            obstacles.append({
                'id': f'obstacle_{idx}',
                'position': {
                    'x': float(np.mean(x_coords)),
                    'y': float(np.mean(y_coords))
                },
                'dimensions': {
                    'width': float(np.max(x_coords) - np.min(x_coords)),
                    'depth': float(np.max(y_coords) - np.min(y_coords)),
                    'height': float(np.max(heights) - mean_elev)
                },
                'area': float(len(region) * resolution**2),
                'volume': float(np.sum(np.array(heights) - mean_elev) * resolution**2)
            })
        
        return obstacles

    def _flood_fill(
        self,
        grid: np.ndarray,
        start_i: int,
        start_j: int,
        threshold: float,
        visited: np.ndarray
    ) -> List[Tuple[int, int]]:
        region = []
        stack = [(start_i, start_j)]
        
        while stack:
            i, j = stack.pop()
            
            if (i < 0 or i >= grid.shape[0] or
                j < 0 or j >= grid.shape[1] or
                visited[i, j] or
                grid[i, j] <= threshold):
                continue
            
            visited[i, j] = True
            region.append((i, j))
            
            stack.extend([
                (i+1, j), (i-1, j),
                (i, j+1), (i, j-1)
            ])
        
        return region

    def _classify_terrain(
        self,
        avg_slope: float,
        roughness: float,
        obstacle_count: int
    ) -> str:
        if obstacle_count > 10:
            return 'obstacle_field'
        
        for terrain_type, criteria in self.terrain_types.items():
            if (avg_slope <= criteria['max_slope'] and 
                roughness <= criteria['roughness']):
                return terrain_type
        
        return 'rough'

    def _calculate_traversability_score(
        self,
        slope_degrees: np.ndarray,
        roughness: float,
        obstacles: List[Dict]
    ) -> float:
        slope_score = 1.0 - np.clip(np.mean(slope_degrees) / 30.0, 0, 1)
        
        roughness_score = 1.0 - np.clip(roughness / 100.0, 0, 1)
        
        obstacle_penalty = len(obstacles) * 0.05
        obstacle_score = 1.0 - min(obstacle_penalty, 0.5)
        
        total_score = (slope_score * 0.4 + roughness_score * 0.3 + obstacle_score * 0.3) * 100
        
        return float(max(0, min(100, total_score)))

    def _identify_passable_regions(
        self,
        slope_degrees: np.ndarray,
        roughness: float,
        max_slope: float,
        max_roughness: float
    ) -> List[Dict]:
        regions = []
        
        if roughness > max_roughness:
            return regions
        
        passable_mask = slope_degrees <= max_slope
        
        visited = np.zeros_like(passable_mask, dtype=bool)
        
        for i in range(passable_mask.shape[0]):
            for j in range(passable_mask.shape[1]):
                if passable_mask[i, j] and not visited[i, j]:
                    region = self._flood_fill_mask(passable_mask, i, j, visited)
                    if len(region) > 10:
                        regions.append({
                            'size': len(region),
                            'center': {
                                'x': float(np.mean([p[0] for p in region])),
                                'y': float(np.mean([p[1] for p in region]))
                            }
                        })
        
        return regions

    def _flood_fill_mask(
        self,
        mask: np.ndarray,
        start_i: int,
        start_j: int,
        visited: np.ndarray
    ) -> List[Tuple[int, int]]:
        region = []
        stack = [(start_i, start_j)]
        
        while stack:
            i, j = stack.pop()
            
            if (i < 0 or i >= mask.shape[0] or
                j < 0 or j >= mask.shape[1] or
                visited[i, j] or
                not mask[i, j]):
                continue
            
            visited[i, j] = True
            region.append((i, j))
            
            stack.extend([
                (i+1, j), (i-1, j),
                (i, j+1), (i, j-1)
            ])
        
        return region

    def generate_terrain_profile(
        self,
        start_point: Point2D,
        end_point: Point2D,
        terrain_data: TerrainData,
        num_points: int = 100
    ) -> Dict:
        elevation_grid = self._points_to_grid(terrain_data)
        
        x = np.linspace(start_point.x, end_point.x, num_points)
        y = np.linspace(start_point.y, end_point.y, num_points)
        
        x_indices = np.clip(x / terrain_data.resolution, 0, terrain_data.grid_size - 1).astype(int)
        y_indices = np.clip(y / terrain_data.resolution, 0, terrain_data.grid_size - 1).astype(int)
        
        elevations = elevation_grid[x_indices, y_indices]
        
        distances = np.sqrt((x - x[0])**2 + (y - y[0])**2)
        
        slopes = np.gradient(elevations, distances)
        slope_degrees = np.degrees(np.arctan(slopes))
        
        return {
            'distances': distances.tolist(),
            'elevations': elevations.tolist(),
            'slopes': slope_degrees.tolist(),
            'max_elevation': float(np.max(elevations)),
            'min_elevation': float(np.min(elevations)),
            'elevation_gain': float(np.max(elevations) - np.min(elevations)),
            'max_slope': float(np.max(np.abs(slope_degrees)))
        }
