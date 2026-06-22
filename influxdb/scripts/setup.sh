#!/bin/bash

set -e

echo "开始初始化InfluxDB..."

INFLUX_TOKEN="${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}"
INFLUX_ORG="${DOCKER_INFLUXDB_INIT_ORG}"

echo "等待InfluxDB服务可用..."
until influx ping; do
    echo "等待InfluxDB..."
    sleep 2
done

echo "创建额外的Buckets..."

influx bucket create \
    --name gait_results \
    --org "$INFLUX_ORG" \
    --retention 90d \
    --token "$INFLUX_TOKEN" || true

influx bucket create \
    --name obstacle_assessments \
    --org "$INFLUX_ORG" \
    --retention 90d \
    --token "$INFLUX_TOKEN" || true

influx bucket create \
    --name alerts \
    --org "$INFLUX_ORG" \
    --retention 365d \
    --token "$INFLUX_TOKEN" || true

influx bucket create \
    --name sensor_downsampled_1m \
    --org "$INFLUX_ORG" \
    --retention 365d \
    --token "$INFLUX_TOKEN" || true

influx bucket create \
    --name sensor_downsampled_1h \
    --org "$INFLUX_ORG" \
    --retention 730d \
    --token "$INFLUX_TOKEN" || true

echo "Buckets创建完成"

echo "创建连续查询任务..."

SENSOR_RAW_ID=$(influx bucket list --name sensor_raw --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" | grep sensor_raw | awk '{print $1}')
SENSOR_1M_ID=$(influx bucket list --name sensor_downsampled_1m --org "$INFLUX_ORG" --token "$INFLUX_TOKEN" | grep sensor_downsampled_1m | awk '{print $1}')
SENSOR_1H_ID=$(influx bucket list --name sensor_downsampled_1h --org "$INFLUX_TOKEN" | grep sensor_downsampled_1h | awk '{print $1}')

influx task create \
    --name "sensor_downsample_1m" \
    --org "$INFLUX_ORG" \
    --token "$INFLUX_TOKEN" \
    --every 1m \
    --query "
option task = {name: \"sensor_downsample_1m\", every: 1m}

data = from(bucket: \"sensor_raw\")
    |> range(start: -task.every)
    |> filter(fn: (r) => r._measurement == \"sensor_data\")

mean_data = data
    |> aggregateWindow(every: 1m, fn: mean)
    |> to(bucket: \"sensor_downsampled_1m\", org: \"$INFLUX_ORG\")
" || true

influx task create \
    --name "sensor_downsample_1h" \
    --org "$INFLUX_ORG" \
    --token "$INFLUX_TOKEN" \
    --every 1h \
    --query "
option task = {name: \"sensor_downsample_1h\", every: 1h}

data = from(bucket: \"sensor_raw\")
    |> range(start: -task.every)
    |> filter(fn: (r) => r._measurement == \"sensor_data\")

hourly_data = data
    |> aggregateWindow(every: 1h, fn: mean)
    |> to(bucket: \"sensor_downsampled_1h\", org: \"$INFLUX_ORG\")
" || true

echo "连续查询任务创建完成"

echo "创建数据保留策略设置完成"

echo "InfluxDB初始化完成！"
