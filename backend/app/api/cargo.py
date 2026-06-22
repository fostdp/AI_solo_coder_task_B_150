from fastapi import APIRouter, HTTPException, Body
import logging

from app.models.schemas import (
    CargoGridRequest,
    CargoOptimalRequest,
    CargoHeightRequest,
    CargoMassRequest,
)
from app.analysis.cargo_stability import CargoStabilityAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cargo", tags=["货箱稳定性分析"])


@router.post("/stability-grid", summary="分析货箱位置网格稳定性（热力图数据）")
async def analyze_cargo_stability_grid(request: CargoGridRequest = Body(...)):
    try:
        analyzer = CargoStabilityAnalyzer(request.parameters)
        result = analyzer.analyze_cargo_position_grid(
            payload_mass=request.payload_mass,
            x_range=(request.x_min, request.x_max),
            z_range=(request.z_min, request.z_max),
            grid_resolution=request.grid_resolution,
            body_inclination=request.body_inclination,
        )
        return result
    except Exception as e:
        logger.error(f"货箱稳定性网格分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/optimal-position", summary="寻找最优货箱装载位置")
async def find_optimal_cargo_position(request: CargoOptimalRequest = Body(...)):
    try:
        analyzer = CargoStabilityAnalyzer(request.parameters)
        result = analyzer.find_optimal_cargo_position(
            payload_mass=request.payload_mass,
            body_inclination=request.body_inclination,
        )
        return result
    except Exception as e:
        logger.error(f"寻找最优货箱位置失败: {e}")
        raise HTTPException(status_code=500, detail=f"寻找失败: {str(e)}")


@router.post("/height-effect", summary="分析货箱高度对稳定性的影响")
async def analyze_cargo_height_effect(request: CargoHeightRequest = Body(...)):
    try:
        analyzer = CargoStabilityAnalyzer(request.parameters)
        result = analyzer.analyze_height_effect(
            payload_mass=request.payload_mass,
            cargo_x=request.cargo_x,
            cargo_z=request.cargo_z,
            height_range=(request.height_min, request.height_max),
            num_steps=request.num_steps,
        )
        return result
    except Exception as e:
        logger.error(f"货箱高度影响分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/mass-effect", summary="分析货箱质量对稳定性的影响")
async def analyze_cargo_mass_effect(request: CargoMassRequest = Body(...)):
    try:
        analyzer = CargoStabilityAnalyzer(request.parameters)
        result = analyzer.analyze_mass_effect(
            cargo_x=request.cargo_x,
            cargo_z=request.cargo_z,
            mass_range=(request.mass_min, request.mass_max),
            num_steps=request.num_steps,
            body_inclination=request.body_inclination,
        )
        return result
    except Exception as e:
        logger.error(f"货箱质量影响分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
