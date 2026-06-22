from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List
import logging

from app.models.schemas import (
    ObstacleAssessmentResult,
    ObstacleAssessmentRequest,
    TerrainData,
    JansenParameters
)
from app.analysis.obstacle_analysis import ObstacleAnalyzer
from app.analysis.stability_analysis import StabilityAnalyzer
from app.analysis.terrain_recognition import TerrainRecognizer
from app.core.database import influx_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analysis", tags=["分析评估"])


@router.post("/obstacle", response_model=ObstacleAssessmentResult, summary="越障能力评估")
async def assess_obstacle_clearing(request: ObstacleAssessmentRequest):
    try:
        analyzer = ObstacleAnalyzer(request.parameters)
        result = analyzer.assess_obstacle_clearing(request)
        
        await influx_db.write_obstacle_assessment(result)
        
        return result
    except Exception as e:
        logger.error(f"越障评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"越障评估失败: {str(e)}")


@router.post("/terrain", summary="地形分析")
async def analyze_terrain(terrain_data: TerrainData):
    try:
        recognizer = TerrainRecognizer()
        analysis = recognizer.analyze_terrain(terrain_data)
        return analysis
    except Exception as e:
        logger.error(f"地形分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"地形分析失败: {str(e)}")


@router.post("/stability/static", summary="静态稳定性分析")
async def analyze_static_stability(
    crank_angle: float = Query(..., ge=0, le=360, description="曲柄转角"),
    body_inclination: float = Query(0.0, description="机身倾角"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = StabilityAnalyzer(parameters)
        result = analyzer.analyze_static_stability(crank_angle, body_inclination)
        return result
    except Exception as e:
        logger.error(f"静态稳定性分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.get("/stability/critical-inclination", summary="计算临界倾角")
async def calculate_critical_inclination(
    crank_angle: float = Query(..., ge=0, le=360, description="曲柄转角"),
    direction: str = Query("pitch", description="方向: pitch或roll"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = StabilityAnalyzer(parameters)
        critical_angle = analyzer.calculate_critical_inclination(crank_angle, direction)
        return {
            "crank_angle": crank_angle,
            "direction": direction,
            "critical_inclination": critical_angle,
            "safety_margin": critical_angle * 0.8
        }
    except Exception as e:
        logger.error(f"临界倾角计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/stability/ellipsoid", summary="计算稳定椭球")
async def compute_stability_ellipsoid(
    crank_angle: float = Query(..., ge=0, le=360, description="曲柄转角"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = StabilityAnalyzer(parameters)
        ellipsoid = analyzer.compute_stability_ellipsoid(crank_angle)
        return ellipsoid
    except Exception as e:
        logger.error(f"稳定椭球计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/stability/evolution", summary="预测稳定性演化")
async def predict_stability_evolution(
    current_inclination: float = Query(0.0, description="当前倾角"),
    target_inclination: float = Query(10.0, description="目标倾角"),
    duration: float = Query(10.0, description="持续时间(s)"),
    crank_speed: float = Query(30.0, description="曲柄转速"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters(crank_speed=crank_speed)
        analyzer = StabilityAnalyzer(parameters)
        evolution = analyzer.predict_stability_evolution(
            current_inclination=current_inclination,
            target_inclination=target_inclination,
            duration=duration,
            crank_speed=crank_speed
        )
        return evolution
    except Exception as e:
        logger.error(f"稳定性演化预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.post("/obstacle/simulate", summary="越障过程仿真")
async def simulate_obstacle_traversal(
    obstacle_height: float = Query(..., description="障碍高度(mm)"),
    obstacle_width: float = Query(200.0, description="障碍宽度(mm)"),
    approach_speed: float = Query(30.0, description="接近速度"),
    body_inclination: float = Query(0.0, description="机身倾角"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = ObstacleAnalyzer(parameters)
        simulation = analyzer.simulate_obstacle_traversal(
            obstacle_height=obstacle_height,
            obstacle_width=obstacle_width,
            approach_speed=approach_speed,
            body_inclination=body_inclination
        )
        return simulation
    except Exception as e:
        logger.error(f"越障仿真失败: {e}")
        raise HTTPException(status_code=500, detail=f"仿真失败: {str(e)}")


@router.post("/obstacle/optimize", summary="优化越障策略")
async def optimize_obstacle_approach(
    obstacle_height: float = Query(..., description="障碍高度(mm)"),
    obstacle_width: float = Query(200.0, description="障碍宽度(mm)"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = ObstacleAnalyzer(parameters)
        optimization = analyzer.optimize_obstacle_approach(
            obstacle_height=obstacle_height,
            obstacle_width=obstacle_width
        )
        return optimization
    except Exception as e:
        logger.error(f"越障策略优化失败: {e}")
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


@router.post("/obstacle/impact", summary="计算碰撞影响")
async def calculate_obstacle_impact(
    obstacle_height: float = Query(..., description="障碍高度(mm)"),
    current_speed: float = Query(30.0, description="当前速度"),
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        analyzer = ObstacleAnalyzer(parameters)
        impact = analyzer.calculate_obstacle_impact(
            obstacle_height=obstacle_height,
            current_speed=current_speed
        )
        return impact
    except Exception as e:
        logger.error(f"碰撞影响计算失败: {e}")
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@router.post("/comprehensive", summary="综合评估报告")
async def generate_comprehensive_assessment(
    device_id: str = Query(..., description="设备ID"),
    terrain_data: TerrainData = None,
    parameters: JansenParameters = None
):
    try:
        if parameters is None:
            parameters = JansenParameters()
        if terrain_data is None:
            from app.models.schemas import TerrainPoint
            terrain_data = TerrainData(
                grid_size=50,
                resolution=100.0,
                points=[TerrainPoint(x=0, y=0, elevation=0)]
            )
        
        analyzer = ObstacleAnalyzer(parameters)
        report = analyzer.generate_comprehensive_assessment(
            terrain_data=terrain_data,
            device_id=device_id,
            parameters=parameters
        )
        return report
    except Exception as e:
        logger.error(f"综合评估失败: {e}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.post("/terrain/profile", summary="生成地形剖面图")
async def generate_terrain_profile(
    terrain_data: TerrainData,
    start_x: float = Query(0.0, description="起点X"),
    start_y: float = Query(0.0, description="起点Y"),
    end_x: float = Query(1000.0, description="终点X"),
    end_y: float = Query(500.0, description="终点Y"),
    num_points: int = Query(100, ge=10, le=1000, description="采样点数")
):
    try:
        from app.models.schemas import Point2D
        recognizer = TerrainRecognizer()
        start = Point2D(x=start_x, y=start_y)
        end = Point2D(x=end_x, y=end_y)
        profile = recognizer.generate_terrain_profile(
            start_point=start,
            end_point=end,
            terrain_data=terrain_data,
            num_points=num_points
        )
        return profile
    except Exception as e:
        logger.error(f"地形剖面生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
