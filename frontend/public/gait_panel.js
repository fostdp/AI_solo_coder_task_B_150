window.GaitPanel = (function () {
  let container = null;
  let elements = {};
  let state = {
    crankAngle: 0,
    bodyInclination: 0,
    obstacleHeight: 0,
    isPlaying: false,
    simulationSpeed: 1.0,
    showTrajectory: true,
    showLinkages: true,
    jansenParams: {
      crank_length: 150,
      rocker_length: 250,
      coupler_length: 300,
      ground_link: 200
    },
    gaitData: {
      stride_length: 0,
      cadence: 0,
      walking_speed: 0,
      stability_margin: 0,
      gait_phase: 0,
      phase_name: 'support'
    },
    sensorData: null,
    alerts: []
  };
  let callbacks = {
    onParamChange: null,
    onObstacleAssess: null,
    onRefreshSensor: null,
    onSimulate: null
  };

  function init(containerId, options = {}) {
    container = document.getElementById(containerId);
    if (!container) {
      console.error('[GaitPanel] Container not found:', containerId);
      return;
    }

    if (options.onParamChange) callbacks.onParamChange = options.onParamChange;
    if (options.onObstacleAssess) callbacks.onObstacleAssess = options.onObstacleAssess;
    if (options.onRefreshSensor) callbacks.onRefreshSensor = options.onRefreshSensor;
    if (options.onSimulate) callbacks.onSimulate = options.onSimulate;

    if (options.defaultParams) {
      state.jansenParams = { ...state.jansenParams, ...options.defaultParams };
    }

    _render();
    _bindEvents();
    console.log('[GaitPanel] 初始化完成');
  }

  function _render() {
    container.innerHTML = `
      <div class="gait-panel">
        <div class="panel-section">
          <h3 class="section-title">步态控制</h3>
          <div class="control-row">
            <button id="btn-play" class="btn btn-primary">
              <span class="btn-icon">▶</span>
              <span id="play-text">播放</span>
            </button>
            <button id="btn-reset" class="btn">重置</button>
          </div>
          <div class="control-row">
            <label class="control-label">播放速度</label>
            <input type="range" id="speed-slider" class="slider" min="0.1" max="5" step="0.1" value="1">
            <span id="speed-value" class="slider-value">1.0x</span>
          </div>
          <div class="control-row">
            <label class="control-label">曲柄角度</label>
            <input type="range" id="angle-slider" class="slider" min="0" max="360" step="1" value="0">
            <span id="angle-value" class="slider-value">0°</span>
          </div>
          <div class="control-row">
            <label class="control-label">机身倾角</label>
            <input type="range" id="incline-slider" class="slider" min="-30" max="30" step="0.5" value="0">
            <span id="incline-value" class="slider-value">0°</span>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">机构参数</h3>
          ${_renderParamInput('crank_length', '曲柄长度 (mm)', 150)}
          ${_renderParamInput('rocker_length', '摇杆长度 (mm)', 250)}
          ${_renderParamInput('coupler_length', '连杆长度 (mm)', 300)}
          ${_renderParamInput('ground_link', '基架长度 (mm)', 200)}
        </div>

        <div class="panel-section">
          <h3 class="section-title">显示设置</h3>
          <div class="control-row checkbox-row">
            <label>
              <input type="checkbox" id="show-linkages" checked>
              <span>显示连杆机构</span>
            </label>
          </div>
          <div class="control-row checkbox-row">
            <label>
              <input type="checkbox" id="show-trajectory" checked>
              <span>显示足端轨迹</span>
            </label>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">越障分析</h3>
          <div class="control-row">
            <label class="control-label">障碍物高度</label>
            <input type="range" id="obstacle-slider" class="slider" min="0" max="200" step="1" value="0">
            <span id="obstacle-value" class="slider-value">0mm</span>
          </div>
          <div class="control-row">
            <button id="btn-assess" class="btn btn-warning">评估越障</button>
            <button id="btn-simulate" class="btn">仿真越障</button>
          </div>
          <div id="obstacle-result" class="result-box"></div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">步态分析结果</h3>
          <div class="data-grid">
            <div class="data-item">
              <span class="data-label">步长</span>
              <span id="data-stride" class="data-value">-- mm</span>
            </div>
            <div class="data-item">
              <span class="data-label">步频</span>
              <span id="data-cadence" class="data-value">-- 步/min</span>
            </div>
            <div class="data-item">
              <span class="data-label">行走速度</span>
              <span id="data-speed" class="data-value">-- mm/s</span>
            </div>
            <div class="data-item">
              <span class="data-label">稳定裕度</span>
              <span id="data-margin" class="data-value">-- mm</span>
            </div>
            <div class="data-item">
              <span class="data-label">步态相位</span>
              <span id="data-phase" class="data-value">--</span>
            </div>
            <div class="data-item">
              <span class="data-label">相位名称</span>
              <span id="data-phase-name" class="data-value">--</span>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">传感器数据</h3>
          <div class="control-row">
            <button id="btn-refresh-sensor" class="btn">刷新</button>
          </div>
          <div id="sensor-data" class="sensor-data-box">
            <p class="hint">暂无数据，点击刷新获取</p>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">告警信息</h3>
          <div id="alerts-list" class="alerts-list">
            <p class="hint">当前无告警</p>
          </div>
        </div>
      </div>
    `;

    elements = {
      btnPlay: container.querySelector('#btn-play'),
      playText: container.querySelector('#play-text'),
      btnReset: container.querySelector('#btn-reset'),
      speedSlider: container.querySelector('#speed-slider'),
      speedValue: container.querySelector('#speed-value'),
      angleSlider: container.querySelector('#angle-slider'),
      angleValue: container.querySelector('#angle-value'),
      inclineSlider: container.querySelector('#incline-slider'),
      inclineValue: container.querySelector('#incline-value'),
      showLinkages: container.querySelector('#show-linkages'),
      showTrajectory: container.querySelector('#show-trajectory'),
      obstacleSlider: container.querySelector('#obstacle-slider'),
      obstacleValue: container.querySelector('#obstacle-value'),
      btnAssess: container.querySelector('#btn-assess'),
      btnSimulate: container.querySelector('#btn-simulate'),
      obstacleResult: container.querySelector('#obstacle-result'),
      btnRefreshSensor: container.querySelector('#btn-refresh-sensor'),
      sensorDataBox: container.querySelector('#sensor-data'),
      alertsList: container.querySelector('#alerts-list'),
      dataStride: container.querySelector('#data-stride'),
      dataCadence: container.querySelector('#data-cadence'),
      dataSpeed: container.querySelector('#data-speed'),
      dataMargin: container.querySelector('#data-margin'),
      dataPhase: container.querySelector('#data-phase'),
      dataPhaseName: container.querySelector('#data-phase-name'),
      paramInputs: {
        crank_length: container.querySelector('#param-crank_length'),
        rocker_length: container.querySelector('#param-rocker_length'),
        coupler_length: container.querySelector('#param-coupler_length'),
        ground_link: container.querySelector('#param-ground_link')
      }
    };
  }

  function _renderParamInput(key, label, defaultValue) {
    return `
      <div class="control-row">
        <label class="control-label" for="param-${key}">${label}</label>
        <input type="number" id="param-${key}" class="param-input" value="${defaultValue}" min="10" max="500" step="1">
      </div>
    `;
  }

  function _bindEvents() {
    elements.btnPlay.addEventListener('click', () => {
      state.isPlaying = !state.isPlaying;
      elements.playText.textContent = state.isPlaying ? '暂停' : '播放';
      elements.btnPlay.querySelector('.btn-icon').textContent = state.isPlaying ? '⏸' : '▶';
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ isPlaying: state.isPlaying });
      }
    });

    elements.btnReset.addEventListener('click', () => {
      state.crankAngle = 0;
      state.bodyInclination = 0;
      state.obstacleHeight = 0;
      state.isPlaying = false;
      state.simulationSpeed = 1.0;
      state.showTrajectory = true;
      state.showLinkages = true;

      elements.angleSlider.value = 0;
      elements.angleValue.textContent = '0°';
      elements.inclineSlider.value = 0;
      elements.inclineValue.textContent = '0°';
      elements.obstacleSlider.value = 0;
      elements.obstacleValue.textContent = '0mm';
      elements.speedSlider.value = 1;
      elements.speedValue.textContent = '1.0x';
      elements.showLinkages.checked = true;
      elements.showTrajectory.checked = true;
      elements.playText.textContent = '播放';
      elements.btnPlay.querySelector('.btn-icon').textContent = '▶';

      if (callbacks.onParamChange) {
        callbacks.onParamChange({
          crankAngle: 0,
          bodyInclination: 0,
          obstacleHeight: 0,
          isPlaying: false,
          simulationSpeed: 1.0,
          showTrajectory: true,
          showLinkages: true
        });
      }
    });

    elements.speedSlider.addEventListener('input', (e) => {
      state.simulationSpeed = parseFloat(e.target.value);
      elements.speedValue.textContent = state.simulationSpeed.toFixed(1) + 'x';
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ simulationSpeed: state.simulationSpeed });
      }
    });

    elements.angleSlider.addEventListener('input', (e) => {
      state.crankAngle = parseFloat(e.target.value);
      elements.angleValue.textContent = state.crankAngle.toFixed(0) + '°';
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ crankAngle: state.crankAngle });
      }
    });

    elements.inclineSlider.addEventListener('input', (e) => {
      state.bodyInclination = parseFloat(e.target.value);
      elements.inclineValue.textContent = state.bodyInclination.toFixed(1) + '°';
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ bodyInclination: state.bodyInclination });
      }
    });

    elements.showLinkages.addEventListener('change', (e) => {
      state.showLinkages = e.target.checked;
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ showLinkages: state.showLinkages });
      }
    });

    elements.showTrajectory.addEventListener('change', (e) => {
      state.showTrajectory = e.target.checked;
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ showTrajectory: state.showTrajectory });
      }
    });

    elements.obstacleSlider.addEventListener('input', (e) => {
      state.obstacleHeight = parseFloat(e.target.value);
      elements.obstacleValue.textContent = state.obstacleHeight.toFixed(0) + 'mm';
      if (callbacks.onParamChange) {
        callbacks.onParamChange({ obstacleHeight: state.obstacleHeight });
      }
    });

    Object.keys(elements.paramInputs).forEach(key => {
      elements.paramInputs[key].addEventListener('change', (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
          state.jansenParams[key] = val;
          if (callbacks.onParamChange) {
            callbacks.onParamChange({ jansenParams: { ...state.jansenParams } });
          }
        }
      });
    });

    elements.btnAssess.addEventListener('click', () => {
      if (callbacks.onObstacleAssess) {
        callbacks.onObstacleAssess({
          obstacleHeight: state.obstacleHeight,
          bodyInclination: state.bodyInclination,
          jansenParams: { ...state.jansenParams }
        });
      }
    });

    elements.btnSimulate.addEventListener('click', () => {
      if (callbacks.onSimulate) {
        callbacks.onSimulate({
          obstacleHeight: state.obstacleHeight,
          bodyInclination: state.bodyInclination,
          jansenParams: { ...state.jansenParams }
        });
      }
    });

    elements.btnRefreshSensor.addEventListener('click', () => {
      if (callbacks.onRefreshSensor) {
        callbacks.onRefreshSensor();
      }
    });
  }

  function setCrankAngle(angle) {
    state.crankAngle = angle;
    elements.angleSlider.value = angle;
    elements.angleValue.textContent = angle.toFixed(0) + '°';
  }

  function setGaitData(data) {
    state.gaitData = { ...state.gaitData, ...data };
    if (elements.dataStride && data.stride_length != null) {
      elements.dataStride.textContent = data.stride_length.toFixed(1) + ' mm';
    }
    if (elements.dataCadence && data.cadence != null) {
      elements.dataCadence.textContent = data.cadence.toFixed(1) + ' 步/min';
    }
    if (elements.dataSpeed && data.walking_speed != null) {
      elements.dataSpeed.textContent = data.walking_speed.toFixed(1) + ' mm/s';
    }
    if (elements.dataMargin && data.stability_margin != null) {
      const el = elements.dataMargin;
      el.textContent = data.stability_margin.toFixed(1) + ' mm';
      el.className = 'data-value ' + (data.stability_margin < 20 ? 'text-warning' : (data.stability_margin < 10 ? 'text-danger' : 'text-success'));
    }
    if (elements.dataPhase && data.gait_phase != null) {
      elements.dataPhase.textContent = (data.gait_phase * 100).toFixed(0) + '%';
    }
    if (elements.dataPhaseName && data.phase_name) {
      elements.dataPhaseName.textContent = data.phase_name;
    }
  }

  function setSensorData(data) {
    state.sensorData = data;
    if (!elements.sensorDataBox) return;

    if (!data) {
      elements.sensorDataBox.innerHTML = '<p class="hint">暂无数据</p>';
      return;
    }

    const qualityClass =
      (data.quality_score || 0) >= 80 ? 'text-success' :
      (data.quality_score || 0) >= 60 ? 'text-warning' : 'text-danger';

    elements.sensorDataBox.innerHTML = `
      <div class="sensor-grid">
        <div class="sensor-item">
          <span class="sensor-label">设备ID</span>
          <span class="sensor-value">${data.device_id || '-'}</span>
        </div>
        <div class="sensor-item">
          <span class="sensor-label">曲柄角度</span>
          <span class="sensor-value">${(data.crank_angle || 0).toFixed(1)}°</span>
        </div>
        <div class="sensor-item">
          <span class="sensor-label">腿部位移</span>
          <span class="sensor-value">${(data.leg_displacement || 0).toFixed(1)} mm</span>
        </div>
        <div class="sensor-item">
          <span class="sensor-label">机身倾角</span>
          <span class="sensor-value">${(data.body_inclination || 0).toFixed(1)}°</span>
        </div>
        <div class="sensor-item">
          <span class="sensor-label">地面起伏</span>
          <span class="sensor-value">${(data.ground_elevation || 0).toFixed(1)} mm</span>
        </div>
        <div class="sensor-item">
          <span class="sensor-label">数据质量</span>
          <span class="sensor-value ${qualityClass}">${(data.quality_score || 0).toFixed(0)}/100 (${data.quality_level || '-'})</span>
        </div>
        <div class="sensor-item full">
          <span class="sensor-label">时间</span>
          <span class="sensor-value">${data.timestamp ? new Date(data.timestamp).toLocaleString() : '-'}</span>
        </div>
      </div>
    `;
  }

  function setObstacleResult(result) {
    if (!elements.obstacleResult) return;

    if (!result) {
      elements.obstacleResult.innerHTML = '';
      return;
    }

    const riskClass =
      result.risk_level === 'low' ? 'text-success' :
      result.risk_level === 'medium' ? 'text-warning' : 'text-danger';

    elements.obstacleResult.innerHTML = `
      <div class="result-grid">
        <div class="result-item">
          <span class="result-label">最大可越高度</span>
          <span class="result-value">${(result.max_obstacle_height || 0).toFixed(1)} mm</span>
        </div>
        <div class="result-item">
          <span class="result-label">最大坡度</span>
          <span class="result-value">${(result.max_slope_angle || 0).toFixed(1)}°</span>
        </div>
        <div class="result-item">
          <span class="result-label">临界倾角</span>
          <span class="result-value">${(result.critical_inclination || 0).toFixed(1)}°</span>
        </div>
        <div class="result-item">
          <span class="result-label">通过概率</span>
          <span class="result-value">${((result.obstacle_pass_probability || 0) * 100).toFixed(1)}%</span>
        </div>
        <div class="result-item">
          <span class="result-label">风险等级</span>
          <span class="result-value ${riskClass}">${result.risk_level || '-'}</span>
        </div>
        <div class="result-item">
          <span class="result-label">推荐速度</span>
          <span class="result-value">${(result.recommended_speed || 0).toFixed(1)} mm/s</span>
        </div>
      </div>
    `;
  }

  function addAlert(alert) {
    state.alerts.unshift(alert);
    if (state.alerts.length > 50) state.alerts = state.alerts.slice(0, 50);
    _renderAlerts();
  }

  function clearAlert(alertId) {
    state.alerts = state.alerts.filter(a => a.alert_id !== alertId);
    _renderAlerts();
  }

  function setAlerts(alerts) {
    state.alerts = alerts || [];
    _renderAlerts();
  }

  function _renderAlerts() {
    if (!elements.alertsList) return;

    if (state.alerts.length === 0) {
      elements.alertsList.innerHTML = '<p class="hint">当前无告警</p>';
      return;
    }

    elements.alertsList.innerHTML = state.alerts.slice(0, 10).map(alert => {
      const sevClass =
        alert.severity === 'critical' ? 'alert-critical' :
        alert.severity === 'warning' ? 'alert-warning' : 'alert-info';
      const statusIcon = alert.is_active === false ? '✓' : '⚠';

      return `
        <div class="alert-item ${sevClass}">
          <span class="alert-icon">${statusIcon}</span>
          <div class="alert-content">
            <div class="alert-title">${alert.message || alert.alert_type}</div>
            <div class="alert-meta">
              <span class="alert-device">${alert.device_id || '-'}</span>
              <span class="alert-time">${alert.triggered_at ? new Date(alert.triggered_at).toLocaleTimeString() : '-'}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  function getState() {
    return { ...state };
  }

  return {
    init,
    setCrankAngle,
    setGaitData,
    setSensorData,
    setObstacleResult,
    addAlert,
    clearAlert,
    setAlerts,
    getState
  };
})();
