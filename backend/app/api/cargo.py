from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import (
    JansenParameters,
    CargoGridRequest,
    CargoOptimalRequest,
    CargoHeightRequest,
    CargoMassRequest,
)
from app.analysis.cargo_stability import CargoStabilityAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cargo", tags=["货箱稳定性分析"])


@router.post("/stability-grid", summary="货箱位置网格稳定性分析")
async def analyze_stability_grid(request: CargoGridRequest):
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
        logger.error(f"网格稳定性分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/optimal-position", summary="查找最优货箱位置")
async def find_optimal_position(request: CargoOptimalRequest):
    try:
        analyzer = CargoStabilityAnalyzer(request.parameters)
        result = analyzer.find_optimal_cargo_position(
            payload_mass=request.payload_mass,
            body_inclination=request.body_inclination,
        )
        return result
    except Exception as e:
        logger.error(f"最优位置查找失败: {e}")
        raise HTTPException(status_code=500, detail=f"查找失败: {str(e)}")


@router.post("/height-effect", summary="货箱高度影响分析")
async def analyze_height_effect(request: CargoHeightRequest):
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
        logger.error(f"高度影响分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/mass-effect", summary="货箱质量影响分析")
async def analyze_mass_effect(request: CargoMassRequest):
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
        logger.error(f"质量影响分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
