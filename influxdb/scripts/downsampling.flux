// ============================================================
// InfluxDB 降采样任务配置
// 将高精度原始数据聚合为低精度历史数据，节省存储空间
// ============================================================

// ------------------------------
// 1. 传感器数据 - 5分钟聚合
// ------------------------------
option task = {
    name: "sensor_raw_downsample_5m",
    every: 5m,
    offset: 30s
}

data = from(bucket: "sensor_raw")
    |> range(start: -duration(v: 5m))
    |> filter(fn: (r) => r._measurement == "sensor_data")

// 数值字段聚合
data
    |> filter(fn: (r) =>
        r._field == "crank_angle" or
        r._field == "leg_displacement" or
        r._field == "body_inclination" or
        r._field == "ground_elevation" or
        r._field == "quality_score")
    |> aggregateWindow(
        every: 5m,
        fn: (tables=<-, column) => tables
            |> mean(column: column)
            |> set(key: "_agg", value: "mean"),
        createEmpty: false
    )
    |> to(
        bucket: "sensor_history",
        org: "wood-ox-research",
        timeColumn: "_stop",
        tagColumns: ["device_id", "_field", "_agg"]
    )

data
    |> filter(fn: (r) =>
        r._field == "crank_angle" or
        r._field == "leg_displacement" or
        r._field == "body_inclination" or
        r._field == "ground_elevation")
    |> aggregateWindow(
        every: 5m,
        fn: (tables=<-, column) => tables
            |> min(column: column)
            |> set(key: "_agg", value: "min"),
        createEmpty: false
    )
    |> to(
        bucket: "sensor_history",
        org: "wood-ox-research",
        timeColumn: "_stop",
        tagColumns: ["device_id", "_field", "_agg"]
    )

data
    |> filter(fn: (r) =>
        r._field == "crank_angle" or
        r._field == "leg_displacement" or
        r._field == "body_inclination" or
        r._field == "ground_elevation")
    |> aggregateWindow(
        every: 5m,
        fn: (tables=<-, column) => tables
            |> max(column: column)
            |> set(key: "_agg", value: "max"),
        createEmpty: false
    )
    |> to(
        bucket: "sensor_history",
        org: "wood-ox-research",
        timeColumn: "_stop",
        tagColumns: ["device_id", "_field", "_agg"]
    )


// ------------------------------
// 2. 步态数据 - 5分钟聚合
// ------------------------------
option task = {
    name: "gait_downsample_5m",
    every: 5m,
    offset: 30s
}

gait = from(bucket: "sensor_raw")
    |> range(start: -duration(v: 5m))
    |> filter(fn: (r) => r._measurement == "gait_result")

gait
    |> filter(fn: (r) =>
        r._field == "stride_length" or
        r._field == "cadence" or
        r._field == "walking_speed" or
        r._field == "stability_margin" or
        r._field == "gait_symmetry")
    |> aggregateWindow(
        every: 5m,
        fn: (tables=<-, column) => tables
            |> mean(column: column)
            |> set(key: "_agg", value: "mean"),
        createEmpty: false
    )
    |> to(
        bucket: "sensor_history",
        org: "wood-ox-research",
        timeColumn: "_stop",
        tagColumns: ["device_id", "_field", "_agg"]
    )


// ------------------------------
// 3. 告警统计 - 1小时聚合
// ------------------------------
option task = {
    name: "alert_downsample_1h",
    every: 1h,
    offset: 1m
}

alerts = from(bucket: "sensor_raw")
    |> range(start: -duration(v: 1h))
    |> filter(fn: (r) => r._measurement == "alert_event")

alerts
    |> filter(fn: (r) => r._field == "is_active")
    |> aggregateWindow(
        every: 1h,
        fn: (tables=<-, column) => tables
            |> count(column: column)
            |> set(key: "_agg", value: "count"),
        createEmpty: false
    )
    |> to(
        bucket: "sensor_history",
        org: "wood-ox-research",
        timeColumn: "_stop",
        tagColumns: ["device_id", "alert_type", "severity", "_agg"]
    )


// ------------------------------
// 4. 数据保留策略 - 30天后自动清理原始数据
// ------------------------------
// 注：需要在InfluxDB中执行:
// influx bucket update --id <sensor_raw_bucket_id> --retention 720h
// 或通过Web UI配置
