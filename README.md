# 古代木牛流马行走机构仿真与越障能力分析系统

一套用于三国时期木牛流马复原研究的全栈仿真分析系统，基于 Jansen 连杆理论和多体动力学，实现行走机构仿真、越障能力评估和实时告警功能。采用微服务架构，支持 Modbus RTU / MQTT / HTTP 多协议传感器数据采集。

---

## 目录

- [系统架构](#系统架构)
- [功能特性](#功能特性)
- [快速部署](#快速部署)
  - [环境要求](#环境要求)
  - [一键启动（单体模式）](#一键启动单体模式)
  - [全功能部署（含模拟器）](#全功能部署含模拟器)
  - [分布式微服务部署](#分布式微服务部署)
- [传感器模拟器](#传感器模拟器)
  - [地形类型](#地形类型)
  - [负载等级](#负载等级)
  - [使用方法](#使用方法)
- [InfluxDB 降采样](#influxdb-降采样)
- [API 接口](#api-接口)
- [开发指南](#开发指南)
- [目录结构](#目录结构)

---

## 系统架构

### 整体架构图

```
                          ┌─────────────────────────────────────────────────────────┐
                          │                        前端 (React + Three.js)           │
                          │  wooden_ox_3d.js (3D渲染)  |  gait_panel.js (控制面板)  │
                          └───────────────────────────┬─────────────────────────────┘
                                                      │ HTTP / WebSocket
                                                      ▼
┌──────────────┐   HTTP   ┌──────────────────────────────────────────────────────────┐
│              │ ◄──────► │                    API Gateway (FastAPI)                 │
│   浏览器      │  WS      │   gunicorn + uvicorn workers (多进程)                   │
│              │          └──────┬───────────────────┬───────────────────┬───────────┘
└──────────────┘                 │                   │                   │
                                 ▼                   ▼                   ▼
                       ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
                       │  Redis Pub/Sub   │ │   InfluxDB 2.x   │ │  Mosquitto MQTT  │
                       │  微服务消息总线   │ │   时序数据存储    │ │   消息代理 Broker │
                       └────────┬─────────┘ └──────────────────┘ └────────┬─────────┘
                                │ 订阅/发布                                   │ 订阅
                                │                                            ▼
           ┌────────────────────┼────────────────────┬──────────────────────────────┐
           ▼                    ▼                    ▼                              │
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            ┌──────────▼───────┐
│ modbus_receiver  │ │walking_simulator │ │obstacle_analyzer │            │  传感器模拟器    │
│ 数据采集 & 校验   │ │ 动力学 & 步态计算 │ │ 地形识别 & 越障   │◄───────────┤  (多设备并发)    │
└────────┬─────────┘ └─────────┬────────┘ └─────────┬────────┘  Modbus/MQTT  └──────────────────┘
         │                     │                     │               HTTP
         ▼                     ▼                     ▼
   SENSOR_VALIDATED       GAIT_RESULT           OBSTACLE_RESULT
         │                     │                     │
         └─────────────────────┴─────────────────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │    alarm_ws      │
                      │ 告警 & WebSocket │
                      └────────┬─────────┘
                               │ WebSocket 推送
                               ▼
                          前端告警面板
```

### 微服务模块说明

| 服务 | 职责 | 订阅频道 | 发布频道 |
|------|------|---------|---------|
| **modbus_receiver** | Modbus RTU 数据采集、数据质量校验 | - | `SENSOR_VALIDATED` |
| **walking_simulator** | Jansen 连杆求解、多体动力学、步态分析 | `SENSOR_VALIDATED` | `GAIT_RESULT`, `DYNAMICS_RESULT` |
| **obstacle_analyzer** | 地形识别、越障评估、障碍通过概率 | `SENSOR_VALIDATED` | `TERRAIN_RESULT`, `OBSTACLE_RESULT` |
| **alarm_ws** | 告警触发/清除、WebSocket 实时推送 | `SENSOR_VALIDATED`, `GAIT_RESULT`, `OBSTACLE_RESULT`, `TERRAIN_RESULT` | `ALERT_TRIGGERED`, `ALERT_CLEARED` |

---

## 功能特性

- ✅ **Jansen 连杆理论**：精确求解八连杆机构运动学，足端轨迹仿真
- ✅ **多体动力学**：重心（COM）、零力矩点（ZMP）、稳定裕度、关节力矩计算
- ✅ **地面接触模型**：赫兹接触理论、库仑摩擦、打滑检测
- ✅ **变重心控制**：负载质量影响、COM 动态调整、倾角补偿
- ✅ **FABRIK IK 解算器**：前端逆运动学调试面板
- ✅ **地形识别与越障评估**：8种地形模式、最大可越高度、通过概率、风险等级
- ✅ **实时告警**：机身倾角过大、机构卡死、稳定裕度过低触发告警，WebSocket 推送
- ✅ **多协议数据采集**：Modbus RTU/TCP、HTTP REST API、MQTT
- ✅ **生产级部署**：Python 多阶段构建、Gunicorn + Uvicorn、Nginx Gzip/Brotli、InfluxDB 降采样
- ✅ **可配置传感器模拟器**：8种地形、5种负载等级、多设备并发

---

## 快速部署

### 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Docker | 20.10+ | 容器运行时 |
| Docker Compose | 2.0+ | 编排工具 |
| 内存 | ≥ 4GB | InfluxDB + Redis + 后端 + 模拟器 |
| 磁盘 | ≥ 10GB | 时序数据存储 |

### 一键启动（单体模式）

启动基础服务：InfluxDB、Redis、MQTT Broker、后端 API（单体模式，所有微服务集成在 FastAPI 进程内）

```bash
# 克隆项目
git clone <repo-url>
cd AI_solo_coder_task_A_150

# 启动基础服务
docker-compose up -d influxdb redis mqtt-broker backend

# 查看服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f backend
```

启动成功后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 系统信息：http://localhost:8000/api/info

### 全功能部署（含模拟器）

启动基础服务 + 前端 + 4台不同地形/负载的传感器模拟器：

```bash
# 启动全部（基础服务 + 前端 + 模拟器）
docker-compose --profile simulators --profile frontend up -d

# 或者只启动基础服务 + 模拟器
docker-compose --profile simulators up -d
```

启动的模拟器实例：

| 容器名 | 设备ID | 地形 | 负载 |
|--------|--------|------|------|
| woodox-sim-001-flat | woodox_001 | 平坦路面 | 空载 |
| woodox-sim-002-slope | woodox_002 | 缓坡 | 轻载 |
| woodox-sim-003-rocky | woodox_003 | 岩石路面 | 重载 |
| woodox-sim-004-obstacle | woodox_004 | 障碍路面 | 超载 |

访问前端界面：http://localhost:8080

### 分布式微服务部署

将4个微服务拆分为独立容器部署，通过 Redis Pub/Sub 通信：

```bash
# 启动分布式微服务（替代单体 backend 的集成模式）
docker-compose --profile distributed up -d

# 查看各微服务日志
docker-compose logs -f modbus-receiver walking-simulator obstacle-analyzer alarm-ws
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并清除数据卷 (⚠️ 会丢失 InfluxDB/Redis 数据)
docker-compose down -v
```

---

## 传感器模拟器

增强版传感器模拟器支持多种地形起伏和负载条件，可通过 Modbus TCP、HTTP REST API、MQTT 三种协议上报数据。

### 地形类型

| 地形 | terrain 值 | 说明 | 特征 |
|------|-----------|------|------|
| 平坦路面 | `flat` | 理想测试环境 | 地面起伏 ±5mm，倾角 0° |
| 缓坡 | `gentle_slope` | 轻度坡度 | 最大坡度 5°，起伏 ±10mm |
| 陡坡 | `steep_slope` | 极限坡度测试 | 最大坡度 15°，起伏 ±20mm |
| 岩石路面 | `rocky` | 崎岖 + 小障碍 | 粗糙度 5mm，障碍高度 30mm |
| 泥泞路面 | `muddy` | 低摩擦 + 下沉 | 粗糙度 3mm，随机波动 |
| 混合地形 | `mixed` | 5段循环变化 | 平坦→缓坡→岩石→障碍→陡坡 |
| 阶梯 | `stairs` | 离散高度变化 | 阶梯高度 80mm |
| 越障测试 | `obstacle` | 单一障碍剖面 | 障碍高度 100mm（正弦曲线） |

### 负载等级

| 等级 | load 值 | 负载质量 | 说明 |
|------|---------|---------|------|
| 空载 | `empty` | 0 kg | 基准状态 |
| 轻载 | `light` | 50 kg | 轻微重心偏移 |
| 正常 | `normal` | 150 kg | 标准设计负载 |
| 重载 | `heavy` | 300 kg | 有概率触发 WARNING |
| 超载 | `overload` | 500 kg | 大概率触发告警，可能卡死 |

### 使用方法

#### 方式 1：Docker Compose（推荐）

使用 docker-compose 中已配置的模拟器实例，或自定义：

```yaml
# docker-compose.override.yml
services:
  my-simulator:
    build: ./simulator
    environment:
      DEVICE_ID: woodox_custom_01
      TERRAIN: obstacle        # 地形
      LOAD: heavy              # 负载
      INTERVAL: 3              # 上报间隔(秒)
      PROTOCOL: all            # modbus | http | mqtt | all
      API_URL: http://backend:8000
      MQTT_BROKER: mqtt-broker
      MQTT_PORT: 1883
    depends_on: [backend, mqtt-broker]
```

```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d my-simulator
```

#### 方式 2：命令行本地运行

```bash
cd simulator
pip install -r requirements.txt

# 示例：陡坡 + 重载，每3秒上报，仅MQTT协议
python woodox_simulator.py \
  --device-id woodox_test_01 \
  --terrain steep_slope \
  --load heavy \
  --interval 3 \
  --protocol mqtt \
  --mqtt-broker localhost \
  --api-url http://localhost:8000
```

#### 方式 3：多设备并发（JSON 配置）

创建 `my_devices.json`：

```json
[
  {"device_id": "woodox_A", "terrain": "flat", "load": "normal", "interval": 5},
  {"device_id": "woodox_B", "terrain": "rocky", "load": "heavy", "interval": 5},
  {"device_id": "woodox_C", "terrain": "obstacle", "load": "overload", "interval": 3}
]
```

运行：

```bash
python woodox_simulator.py --config my_devices.json
```

#### MQTT 消息格式

模拟器发布到主题 `woodox/sensor/{device_id}`，payload 为 JSON：

```json
{
  "device_id": "woodox_001",
  "timestamp": "2025-06-22T08:30:00.123456",
  "crank_angle": 45.23,
  "leg_displacement": 298.76,
  "body_inclination": 3.45,
  "ground_elevation": 12.34,
  "status": 1,
  "load_mass": 150.0,
  "load_level": "normal",
  "terrain_type": "flat",
  "payload_offset": {"x": 0, "y": 0, "z": 30.0}
}
```

---

## InfluxDB 降采样

系统配置了三级数据保留策略，通过 Flux Task 实现自动降采样：

### 数据桶

| Bucket | 保留期 | 用途 | 粒度 |
|--------|--------|------|------|
| `sensor_raw` | 30天（可配置） | 原始高精度数据 | 秒级 |
| `sensor_history` | 永久 | 降采样聚合数据 | 5分钟 / 1小时 |

### 降采样任务

任务定义在 [influxdb/scripts/downsampling.flux](file:///d:/SOLO-2/AI_solo_coder_task_A_150/influxdb/scripts/downsampling.flux)

| 任务 | 周期 | 聚合指标 | 存储位置 |
|------|------|---------|---------|
| sensor_raw_downsample_5m | 5分钟 | crank_angle, leg_displacement, body_inclination, ground_elevation, quality_score 的 mean/min/max | sensor_history |
| gait_downsample_5m | 5分钟 | stride_length, cadence, walking_speed, stability_margin 的 mean | sensor_history |
| alert_downsample_1h | 1小时 | 告警事件 count（按类型/严重级别分组） | sensor_history |

### 配置方法

1. 登录 InfluxDB Web UI：http://localhost:8086 （账号 admin / 密码 woodox2024）
2. 左侧菜单 **Tasks** → **Create Task** → **New Task**
3. 粘贴 `downsampling.flux` 内容 → 保存并启用
4. 配置数据保留期：
   ```bash
   # 进入 InfluxDB 容器
   docker exec -it woodox-influxdb influx v1 shell

   # 设置 sensor_raw 保留 30天
   influx bucket update \
     --name sensor_raw \
     --org wood-ox-research \
     --retention 720h

   # 创建 sensor_history bucket (永久保留)
   influx bucket create \
     --name sensor_history \
     --org wood-ox-research \
     --retention 0
   ```

---

## API 接口

完整文档：http://localhost:8000/docs

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/api/info` | 系统信息 |
| POST | `/api/sensors/ingest` | 上报传感器数据 |
| GET | `/api/sensors/latest/{device_id}` | 获取最新传感器数据 |
| POST | `/api/simulation/gait/analyze` | 步态分析 |
| POST | `/api/simulation/linkage/state` | 获取连杆状态 |
| POST | `/api/simulation/obstacle/assess` | 越障评估 |
| GET | `/api/alerts/active` | 获取活跃告警 |
| GET | `/api/alerts/history` | 获取告警历史 |
| WS | `/ws/alerts` | 告警 WebSocket 推送 |

### 示例：上报传感器数据

```bash
curl -X POST http://localhost:8000/api/sensors/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-06-22T08:30:00Z",
    "device_id": "woodox_test",
    "crank_angle": 45.0,
    "leg_displacement": 300.0,
    "body_inclination": 2.5,
    "ground_elevation": 10.0,
    "load_mass": 150.0,
    "terrain_type": "flat"
  }'
```

---

## 开发指南

### 后端本地开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export APP_ENV=development
export INFLUXDB_URL=http://localhost:8086
export REDIS_URL=redis://localhost:6379/0
export CONFIG_DIR=../config

# 开发模式 (uvicorn 自动重载)
chmod +x entrypoint.sh
APP_ENV=development ./entrypoint.sh
# 或者直接：
uvicorn main:app --reload --port 8000
```

### 前端本地开发

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev
# 访问 http://localhost:3000

# 生产构建（含 Gzip/Brotli 预压缩）
npm run build
# 产物在 dist/ 目录
```

### 运行测试

```bash
# 核心算法测试
python test_core_modules.py

# 微服务架构测试
python test_microservices.py
```

---

## 目录结构

```
AI_solo_coder_task_A_150/
├── backend/                          # 后端 Python 代码
│   ├── app/
│   │   ├── api/                      # API 路由层
│   │   ├── core/                     # 核心基础设施
│   │   │   ├── config_loader.py      # JSON 配置加载
│   │   │   ├── database.py           # InfluxDB/Redis 客户端
│   │   │   ├── message_bus.py        # Redis Pub/Sub 消息总线
│   │   │   └── websocket.py          # WebSocket 管理
│   │   ├── models/                   # Pydantic 数据模型
│   │   ├── services/                 # 业务服务层
│   │   │   ├── mqtt_bridge.py        # MQTT→API 桥接
│   │   │   └── modbus_client.py      # Modbus 客户端
│   │   ├── simulation/               # 仿真核心
│   │   │   ├── jansen_linkage.py     # Jansen 连杆求解
│   │   │   ├── multibody_dynamics.py # 多体动力学
│   │   │   └── gait_engine.py        # 步态引擎
│   │   └── analysis/                 # 分析模块
│   ├── microservices/                # 微服务独立进程
│   │   ├── modbus_receiver.py        # 数据采集服务
│   │   ├── walking_simulator.py      # 动力学服务
│   │   ├── obstacle_analyzer.py      # 越障分析服务
│   │   └── alarm_ws.py               # 告警推送服务
│   ├── Dockerfile                    # 多阶段构建 Dockerfile
│   ├── gunicorn_conf.py              # Gunicorn 配置
│   ├── entrypoint.sh                 # 入口脚本
│   ├── main.py                       # API 网关入口
│   └── requirements.txt
├── frontend/                         # 前端 React + Three.js
│   ├── public/
│   │   ├── wooden_ox_3d.js           # 3D 渲染模块
│   │   └── gait_panel.js             # 控制面板模块
│   ├── src/
│   ├── Dockerfile                    # Nginx + Gzip 生产部署
│   ├── nginx.conf                    # Nginx 主配置 (含 Gzip)
│   ├── default.conf                  # Nginx 站点配置
│   ├── vite.config.ts                # Vite 配置 (含 Gzip/Brotli 插件)
│   └── package.json
├── simulator/                        # 传感器模拟器
│   ├── woodox_simulator.py           # 增强版模拟器（地形+负载）
│   ├── devices_config.json           # 多设备配置示例
│   ├── Dockerfile
│   └── requirements.txt
├── config/                           # 外置 JSON 配置
│   ├── mechanism_params.json         # 机构参数
│   └── terrain_params.json           # 地形参数
├── influxdb/                         # InfluxDB 相关
│   └── scripts/
│       ├── setup.sh                  # 初始化脚本
│       └── downsampling.flux         # 降采样任务
├── mqtt/                             # MQTT Broker 配置
│   ├── mosquitto.conf
│   ├── passwd
│   └── acl
├── docker-compose.yml                # 统一编排
├── test_core_modules.py              # 核心算法测试
└── test_microservices.py             # 微服务架构测试
```

---

## License

MIT License - 仅供学术研究使用
