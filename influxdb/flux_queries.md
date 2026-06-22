# InfluxDB Flux 查询模板

## 传感器数据查询

### 查询最新传感器数据
```flux
from(bucket: "sensor_raw")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
```

### 查询历史传感器数据
```flux
from(bucket: "sensor_raw")
  |> range(start: 2024-01-01T00:00:00Z, stop: 2024-01-01T01:00:00Z)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> limit(n: 1000)
```

### 查询1分钟降采样数据
```flux
from(bucket: "sensor_downsampled_1m")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

## 告警查询

### 查询活动告警
```flux
from(bucket: "alerts")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "alerts")
  |> filter(fn: (r) => r.acknowledged == "false")
  |> sort(columns: ["_time"], desc: true)
```

### 按类型查询告警
```flux
from(bucket: "alerts")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "alerts")
  |> filter(fn: (r) => r.type == "INCLINATION_EXCEEDED")
  |> sort(columns: ["_time"], desc: true)
```

### 告警统计
```flux
from(bucket: "alerts")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "alerts")
  |> group(columns: ["type"])
  |> count()
  |> keep(columns: ["type", "_value"])
```

## 步态分析查询

### 查询步态分析结果
```flux
from(bucket: "gait_results")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "gait_results")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
```

### 步态稳定性趋势
```flux
from(bucket: "gait_results")
  |> range(start: -6h)
  |> filter(fn: (r) => r._measurement == "gait_results")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> filter(fn: (r) => r._field == "stability_margin")
  |> movingAverage(n: 10)
```

## 越障评估查询

### 查询越障评估结果
```flux
from(bucket: "obstacle_assessments")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "obstacle_assessments")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
```

### 最大越障高度趋势
```flux
from(bucket: "obstacle_assessments")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "obstacle_assessments")
  |> filter(fn: (r) => r._field == "max_obstacle_height")
  |> aggregateWindow(every: 1h, fn: mean)
```

## 聚合查询

### 计算统计指标
```flux
from(bucket: "sensor_raw")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r.device_id == "woodox_001")
  |> aggregateWindow(
      every: 5m,
      fn: (column, tables=<-) => ({
          mean: tables |> mean(column: column),
          min: tables |> min(column: column),
          max: tables |> max(column: column),
          stddev: tables |> stddev(column: column)
      })
  )
```

### 机身倾角超限检测
```flux
from(bucket: "sensor_raw")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "body_inclination")
  |> filter(fn: (r) => math.abs(x: r._value) > 15.0)
  |> sort(columns: ["_time"], desc: true)
```

### 曲柄转角变化率
```flux
from(bucket: "sensor_raw")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "crank_angle")
  |> derivative(unit: 1s, nonNegative: false)
  |> map(fn: (r) => ({r with angular_velocity: r._value}))
```

## 多设备比较

### 多设备数据对比
```flux
data = from(bucket: "sensor_raw")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> filter(fn: (r) => r._field == "body_inclination")
  |> keep(columns: ["_time", "device_id", "_value"])

data
  |> group(columns: ["device_id"])
  |> mean()
  |> keep(columns: ["device_id", "_value"])
  |> rename(columns: {_value: "avg_inclination"})
```

### 设备可用性统计
```flux
from(bucket: "sensor_raw")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "sensor_data")
  |> group(columns: ["device_id"])
  |> count()
  |> keep(columns: ["device_id", "_value"])
  |> rename(columns: {_value: "data_points"})
  |> map(fn: (r) => ({r with availability: r._value / 1440.0 * 100.0}))
```
