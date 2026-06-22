from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from app.models.schemas import JansenParameters
from app.analysis.transport_comparison import TransportComparisonAnalyzer
from app.analysis.era_comparison import EraComparisonAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/comparison", tags=["对比分析"])


@router.post("/transport/obstacle-clearing", summary="运输工具越障对比")
async def compare_obstacle_clearing(terrain_data: dict):
    try:
        analyzer = TransportComparisonAnalyzer()
        result = analyzer.compare_obstacle_clearing(terrain_data)
        return result
    except Exception as e:
        logger.error(f"越障对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"越障对比失败: {str(e)}")


@router.get("/transport/terrain", summary="运输工具地形对比")
async def compare_on_terrain(
    terrain_type: str = Query("flat", description="地形类型"),
    crank_length: float = Query(150.0, description="曲柄长度"),
    rocker_length: float = Query(250.0, description="摇杆长度"),
    coupler_length: float = Query(300.0, description="连杆长度"),
    ground_link: float = Query(200.0, description="机架长度"),
):
    try:
        params = JansenParameters(
            crank_length=crank_length,
            rocker_length=rocker_length,
            coupler_length=coupler_length,
            ground_link=ground_link,
        )
        analyzer = TransportComparisonAnalyzer(params)
        result = analyzer.compare_on_terrain(terrain_type)
        return result
    except Exception as e:
        logger.error(f"地形对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"地形对比失败: {str(e)}")


@router.get("/transport/profiles", summary="获取运输工具参数")
async def get_transport_profiles():
    try:
        analyzer = TransportComparisonAnalyzer()
        result = analyzer.get_transport_profiles()
        return result
    except Exception as e:
        logger.error(f"获取运输工具参数失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取参数失败: {str(e)}")


@router.get("/transport/radar", summary="运输工具雷达图")
async def generate_transport_radar(
    terrain_type: str = Query("flat", description="地形类型"),
):
    try:
        analyzer = TransportComparisonAnalyzer()
        result = analyzer.generate_radar_data(terrain_type)
        return result
    except Exception as e:
        logger.error(f"雷达图生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"雷达图生成失败: {str(e)}")


@router.get("/era/all-metrics", summary="时代全指标对比")
async def compare_all_era_metrics(
    crank_length: Optional[float] = Query(None, description="曲柄长度"),
    rocker_length: Optional[float] = Query(None, description="摇杆长度"),
    coupler_length: Optional[float] = Query(None, description="连杆长度"),
    ground_link: Optional[float] = Query(None, description="机架长度"),
):
    try:
        params = None
        if crank_length is not None:
            params = JansenParameters(
                crank_length=crank_length,
                rocker_length=rocker_length or 250.0,
                coupler_length=coupler_length or 300.0,
                ground_link=ground_link or 200.0,
            )
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_all_metrics(params)
        return result
    except Exception as e:
        logger.error(f"时代指标对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"对比失败: {str(e)}")


@router.get("/era/radar", summary="时代雷达图")
async def generate_era_radar(
    crank_length: Optional[float] = Query(None, description="曲柄长度"),
    rocker_length: Optional[float] = Query(None, description="摇杆长度"),
    coupler_length: Optional[float] = Query(None, description="连杆长度"),
    ground_link: Optional[float] = Query(None, description="机架长度"),
):
    try:
        params = None
        if crank_length is not None:
            params = JansenParameters(
                crank_length=crank_length,
                rocker_length=rocker_length or 250.0,
                coupler_length=coupler_length or 300.0,
                ground_link=ground_link or 200.0,
            )
        analyzer = EraComparisonAnalyzer()
        result = analyzer.generate_era_radar(params)
        return result
    except Exception as e:
        logger.error(f"时代雷达图失败: {e}")
        raise HTTPException(status_code=500, detail=f"雷达图失败: {str(e)}")


@router.get("/era/timeline", summary="技术发展时间线")
async def generate_era_timeline():
    try:
        analyzer = EraComparisonAnalyzer()
        result = analyzer.generate_timeline()
        return result
    except Exception as e:
        logger.error(f"时间线生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"时间线生成失败: {str(e)}")


@router.get("/era/mechanism", summary="机构原理对比")
async def compare_mechanism_principle(
    crank_length: Optional[float] = Query(None, description="曲柄长度"),
    rocker_length: Optional[float] = Query(None, description="摇杆长度"),
    coupler_length: Optional[float] = Query(None, description="连杆长度"),
    ground_link: Optional[float] = Query(None, description="机架长度"),
):
    try:
        params = None
        if crank_length is not None:
            params = JansenParameters(
                crank_length=crank_length,
                rocker_length=rocker_length or 250.0,
                coupler_length=coupler_length or 300.0,
                ground_link=ground_link or 200.0,
            )
        analyzer = EraComparisonAnalyzer()
        result = analyzer.compare_mechanism_principle(params)
        return result
    except Exception as e:
        logger.error(f"机构原理对比失败: {e}")
        raise HTTPException(status_code=500, detail=f"机构对比失败: {str(e)}")
