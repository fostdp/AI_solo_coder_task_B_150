from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional
import logging

from app.models.schemas import (
    JansenParameters,
    TransportTerrainProfile,
)
from app.analysis.transport_comparison import TransportComparisonAnalyzer
from app.analysis.era_comparison import EraComparisonAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/comparison", tags=["对比分析"])


@router.post("/transport/obstacle-clearing", summary="古代运输工具越障能力对比")
async def compare_transport_obstacle_clearing(
    terrain_profile: TransportTerrainProfile = Body(...),
    parameters: Optional[JansenParameters] = Body(default=None),
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = TransportComparisonAnalyzer(parameters)
        terrain_data = terrain_profile.model_dump()
        result = analyzer.compare_obstacle_clearing(terrain_data)
        return result
    except Exception as e:
        logger.error(f"运输工具越障对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"对比分析失败: {str(e)}")


@router.get("/transport/terrain", summary="按地形类型对比运输工具")
async def compare_transport_by_terrain(
    terrain_type: str = Query('flat', description="地形类型: flat/gentle_slope/steep_slope/rocky/muddy/stairs/obstacle"),
):
    try:
        analyzer = TransportComparisonAnalyzer()
        result = analyzer.compare_on_terrain(terrain_type)
        return result
    except Exception as e:
        logger.error(f"地形对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"地形对比失败: {str(e)}")


@router.get("/transport/profiles", summary="获取运输工具详细参数档案")
async def get_transport_profiles(
    parameters: Optional[JansenParameters] = None,
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = TransportComparisonAnalyzer(parameters)
        result = analyzer.get_transport_profiles()
        return result
    except Exception as e:
        logger.error(f"获取运输工具档案失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get("/transport/radar", summary="获取运输工具雷达图数据")
async def get_transport_radar(
    terrain_type: str = Query('flat', description="地形类型"),
):
    try:
        analyzer = TransportComparisonAnalyzer()
        result = analyzer.generate_radar_data(terrain_type)
        return result
    except Exception as e:
        logger.error(f"获取雷达图数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取雷达图数据失败: {str(e)}")


@router.get("/era/all-metrics", summary="跨时代对比：木牛流马 vs 现代四足机器人 全部指标")
async def get_era_comparison_all_metrics(
    parameters: Optional[JansenParameters] = None,
):
    try:
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics(parameters)
        return result
    except Exception as e:
        logger.error(f"跨时代对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"跨时代对比失败: {str(e)}")


@router.get("/era/radar", summary="跨时代对比雷达图数据")
async def get_era_radar(
    parameters: Optional[JansenParameters] = None,
):
    try:
        analyzer = EraComparisonAnalyzer()
        result = analyzer.generate_era_radar(parameters)
        return result
    except Exception as e:
        logger.error(f"获取跨时代雷达图失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取雷达图数据失败: {str(e)}")


@router.get("/era/timeline", summary="跨时代发展时间线")
async def get_era_timeline():
    try:
        analyzer = EraComparisonAnalyzer()
        result = analyzer.generate_timeline()
        return result
    except Exception as e:
        logger.error(f"获取时间线失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取时间线失败: {str(e)}")


@router.get("/era/mechanism", summary="跨时代机构原理对比")
async def get_era_mechanism_comparison(
    parameters: Optional[JansenParameters] = None,
):
    try:
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_mechanism_principle(parameters)
        return result
    except Exception as e:
        logger.error(f"机构原理对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"机构原理对比失败: {str(e)}")
