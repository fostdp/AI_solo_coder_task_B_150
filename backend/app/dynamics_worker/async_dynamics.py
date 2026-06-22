import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.models.schemas import (
    JansenParameters,
    Point3D,
    Point2D,
    COMAdjustmentState,
)
from app.simulation.multibody_dynamics import MultibodyDynamics
from .client import DynamicsWorkerClient

logger = logging.getLogger(__name__)


class AsyncMultibodyDynamics:
    def __init__(
        self,
        params: JansenParameters,
        use_worker: bool = True,
        redis_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        self.params = params
        self.use_worker = use_worker
        self._client: Optional[DynamicsWorkerClient] = None
        self._local_dynamics: Optional[MultibodyDynamics] = None
        self._worker_available: Optional[bool] = None
        self._redis_url = redis_url
        self._timeout = timeout

    def _get_local_dynamics(self) -> MultibodyDynamics:
        if self._local_dynamics is None:
            self._local_dynamics = MultibodyDynamics(self.params)
        return self._local_dynamics

    async def _get_client(self) -> Optional[DynamicsWorkerClient]:
        if not self.use_worker:
            return None

        if self._client is None:
            self._client = DynamicsWorkerClient(
                params=self.params,
                redis_url=self._redis_url,
                timeout=self._timeout,
                use_fallback=True
            )
            self._worker_available = await self._client.connect()

        return self._client

    async def _call_method(
        self,
        method_name: str,
        **kwargs: Any
    ) -> Any:
        client = await self._get_client()

        if client and self._worker_available:
            try:
                client_method = getattr(client, method_name)
                return await client_method(**kwargs)
            except Exception as e:
                logger.warning(
                    f"Worker call failed for {method_name}: {e}, "
                    "falling back to local computation"
                )

        local_dynamics = self._get_local_dynamics()
        local_method = getattr(local_dynamics, method_name)
        return await asyncio.to_thread(local_method, **kwargs)

    async def calculate_link_centers_of_mass(
        self,
        joints: Dict[str, Point3D],
        payload_mass: Optional[float] = None,
        payload_offset: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        return await self._call_method(
            'calculate_link_centers_of_mass',
            joints=joints,
            payload_mass=payload_mass,
            payload_offset=payload_offset
        )

    async def calculate_total_center_of_mass(
        self,
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point3D:
        return await self._call_method(
            'calculate_total_center_of_mass',
            com_positions=com_positions,
            body_inclination=body_inclination
        )

    async def calculate_joint_forces(
        self,
        joints: Dict[str, Point3D],
        com_positions: Dict[str, Point3D],
        body_inclination: float = 0.0,
        ground_reaction: Optional[Point3D] = None
    ) -> Dict[str, Point3D]:
        return await self._call_method(
            'calculate_joint_forces',
            joints=joints,
            com_positions=com_positions,
            body_inclination=body_inclination,
            ground_reaction=ground_reaction
        )

    async def calculate_zero_moment_point(
        self,
        com: Point3D,
        forces: Dict[str, Point3D],
        joints: Dict[str, Point3D],
        body_inclination: float = 0.0
    ) -> Point2D:
        return await self._call_method(
            'calculate_zero_moment_point',
            com=com,
            forces=forces,
            joints=joints,
            body_inclination=body_inclination
        )

    async def calculate_support_polygon(
        self,
        joints: Dict[str, Point3D],
        num_legs: int = 4,
        spacing: float = 200.0
    ) -> List[Point2D]:
        return await self._call_method(
            'calculate_support_polygon',
            joints=joints,
            num_legs=num_legs,
            spacing=spacing
        )

    async def calculate_stability_margin(
        self,
        zmp: Point2D,
        support_polygon: List[Point2D]
    ) -> float:
        return await self._call_method(
            'calculate_stability_margin',
            zmp=zmp,
            support_polygon=support_polygon
        )

    async def calculate_joint_torques(
        self,
        crank_angle: float,
        body_inclination: float = 0.0,
        external_load: float = 0.0
    ) -> Dict[str, float]:
        return await self._call_method(
            'calculate_joint_torques',
            crank_angle=crank_angle,
            body_inclination=body_inclination,
            external_load=external_load
        )

    async def simulate_gait_cycle(
        self,
        start_angle: float = 0.0,
        end_angle: float = 360.0,
        num_steps: int = 360,
        body_inclination: float = 0.0
    ) -> Dict[str, List]:
        return await self._call_method(
            'simulate_gait_cycle',
            start_angle=start_angle,
            end_angle=end_angle,
            num_steps=num_steps,
            body_inclination=body_inclination
        )

    async def calculate_kinetic_energy(
        self,
        joint_velocities: Dict[str, Point3D],
        com_positions: Dict[str, Point3D]
    ) -> float:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.calculate_kinetic_energy,
            joint_velocities=joint_velocities,
            com_positions=com_positions
        )

    async def calculate_potential_energy(
        self,
        com_positions: Dict[str, Point3D],
        reference_height: float = 0.0
    ) -> float:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.calculate_potential_energy,
            com_positions=com_positions,
            reference_height=reference_height
        )

    async def calculate_target_com(
        self,
        support_polygon: List[Point2D],
        current_com: Point3D,
        payload_mass: float
    ) -> Point3D:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.calculate_target_com,
            support_polygon=support_polygon,
            current_com=current_com,
            payload_mass=payload_mass
        )

    async def calculate_com_adjustment(
        self,
        current_com: Point3D,
        target_com: Point3D,
        current_stability_margin: float,
        body_inclination: float = 0.0,
        dt: float = 0.01
    ) -> COMAdjustmentState:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.calculate_com_adjustment,
            current_com=current_com,
            target_com=target_com,
            current_stability_margin=current_stability_margin,
            body_inclination=body_inclination,
            dt=dt
        )

    async def apply_com_adjustment(
        self,
        com_positions: Dict[str, Point3D],
        com_adjustment: COMAdjustmentState
    ) -> Dict[str, Point3D]:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.apply_com_adjustment,
            com_positions=com_positions,
            com_adjustment=com_adjustment
        )

    async def compensate_body_inclination(
        self,
        joints: Dict[str, Point3D],
        com_adjustment: COMAdjustmentState
    ) -> Dict[str, Point3D]:
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.compensate_body_inclination,
            joints=joints,
            com_adjustment=com_adjustment
        )

    async def update_linkage_state_with_com(
        self,
        linkage_state,
        body_inclination: float = 0.0,
        num_support_legs: int = 2
    ):
        local_dynamics = self._get_local_dynamics()
        return await asyncio.to_thread(
            local_dynamics.update_linkage_state_with_com,
            linkage_state=linkage_state,
            body_inclination=body_inclination,
            num_support_legs=num_support_legs
        )

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        self._worker_available = None

    async def __aenter__(self) -> 'AsyncMultibodyDynamics':
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
