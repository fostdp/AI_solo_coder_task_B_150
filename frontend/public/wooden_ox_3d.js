window.WoodenOx3D = (function () {
  const DEFAULT_PARAMS = {
    crank_length: 150,
    rocker_length: 250,
    coupler_length: 300,
    ground_link: 200,
    crank_speed: 30
  };

  let scene, camera, renderer, controls;
  let bodyGroup, terrainMesh, trajectoryLine;
  let linkages = [];
  let animationId = null;
  let crankAngle = 0;
  let bodyInclination = 0;
  let obstacleHeight = 0;
  let isPlaying = false;
  let simulationSpeed = 1.0;
  let showTrajectory = true;
  let showLinkages = true;
  let params = { ...DEFAULT_PARAMS };
  let onAngleChange = null;

  function init(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.error('[WoodenOx3D] Container not found:', containerId);
      return;
    }

    params = { ...DEFAULT_PARAMS, ...(options.params || {}) };
    onAngleChange = options.onAngleChange || null;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xE8E4D9);
    scene.fog = new THREE.Fog(0xE8E4D9, 800, 2000);

    camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 1, 5000);
    camera.position.set(400, 300, 400);
    camera.lookAt(100, 100, 0);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    if (window.THREE && THREE.OrbitControls) {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enablePan = true;
      controls.enableZoom = true;
      controls.enableRotate = true;
      controls.minDistance = 100;
      controls.maxDistance = 2000;
      controls.target.set(100, 100, 0);
    }

    _setupLights();
    _createTerrain();
    _createBody();
    _createLinkages();
    _createTrajectory();
    _createGrid();
    _animate();

    window.addEventListener('resize', () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });

    console.log('[WoodenOx3D] 初始化完成');
  }

  function _setupLights() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);

    const directional = new THREE.DirectionalLight(0xffffff, 1);
    directional.position.set(500, 500, 300);
    directional.castShadow = true;
    scene.add(directional);

    const point = new THREE.PointLight(0xFFE4B5, 0.5);
    point.position.set(-200, 300, 200);
    scene.add(point);
  }

  function _createTerrain() {
    const geometry = new THREE.PlaneGeometry(2000, 1000, 100, 50);
    const positions = geometry.attributes.position;

    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i);
      const y = positions.getY(i);
      let height = Math.sin(x * 0.01) * 5 + Math.sin(y * 0.02) * 3;

      if (obstacleHeight > 0) {
        const distToObstacle = Math.abs(x - 400);
        if (distToObstacle < 100) {
          const obstacleProfile = obstacleHeight * Math.cos((distToObstacle / 100) * Math.PI / 2);
          height = Math.max(height, obstacleProfile);
        }
      }

      positions.setZ(i, height);
    }
    geometry.computeVertexNormals();

    const material = new THREE.MeshStandardMaterial({
      color: 0x8B7355,
      roughness: 1,
      metalness: 0,
      flatShading: true
    });

    terrainMesh = new THREE.Mesh(geometry, material);
    terrainMesh.rotation.x = -Math.PI / 2;
    terrainMesh.receiveShadow = true;
    scene.add(terrainMesh);
  }

  function _updateTerrain() {
    if (!terrainMesh) return;
    const positions = terrainMesh.geometry.attributes.position;

    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i);
      const y = positions.getY(i);
      let height = Math.sin(x * 0.01) * 5 + Math.sin(y * 0.02) * 3;

      if (obstacleHeight > 0) {
        const distToObstacle = Math.abs(x - 400);
        if (distToObstacle < 100) {
          const obstacleProfile = obstacleHeight * Math.cos((distToObstacle / 100) * Math.PI / 2);
          height = Math.max(height, obstacleProfile);
        }
      }

      positions.setZ(i, height);
    }
    positions.needsUpdate = true;
    terrainMesh.geometry.computeVertexNormals();
  }

  function _createBody() {
    bodyGroup = new THREE.Group();
    bodyGroup.position.set(100, 0, 0);

    const bodyGeo = new THREE.BoxGeometry(300, 80, 120);
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x8B4513 });
    const body = new THREE.Mesh(bodyGeo, bodyMat);
    body.position.y = 100;
    body.castShadow = true;
    bodyGroup.add(body);

    const headGeo = new THREE.BoxGeometry(60, 50, 80);
    const headMat = new THREE.MeshStandardMaterial({ color: 0x654321 });
    const head = new THREE.Mesh(headGeo, headMat);
    head.position.set(-180, 115, 0);
    head.castShadow = true;
    bodyGroup.add(head);

    scene.add(bodyGroup);
  }

  function _createRod(from, to, color = 0x8B4513, radius = 4) {
    const direction = new THREE.Vector3().subVectors(to, from);
    const length = direction.length();
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 8);
    const material = new THREE.MeshStandardMaterial({ color });
    const rod = new THREE.Mesh(geometry, material);

    rod.position.copy(from).add(to).multiplyScalar(0.5);
    rod.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      direction.clone().normalize()
    );
    rod.castShadow = true;
    return rod;
  }

  function _solveJansenLinkage(angle, p) {
    const rad = (angle * Math.PI) / 180;
    const crankX = p.crank_length * Math.cos(rad);
    const crankY = p.crank_length * Math.sin(rad);

    const joints = {
      A: new THREE.Vector3(0, 0, 0),
      O: new THREE.Vector3(-p.ground_link, 0, 0),
      B: new THREE.Vector3(crankX, crankY, 0)
    };

    const rockerPivot = joints.O;
    const crankEnd = joints.B;
    const groundEnd = joints.A;

    const d = crankEnd.distanceTo(rockerPivot);
    const a = p.rocker_length;
    const b = p.coupler_length;

    let footY = 0;
    if (d > 0 && d < (a + b)) {
      const angleAtPivot = Math.acos(
        Math.max(-1, Math.min(1, (a * a + d * d - b * b) / (2 * a * d)))
      );
      const direction = Math.atan2(crankEnd.y - rockerPivot.y, crankEnd.x - rockerPivot.x);
      const rockerAngle = direction - angleAtPivot;

      joints.C = new THREE.Vector3(
        rockerPivot.x + a * Math.cos(rockerAngle),
        rockerPivot.y + a * Math.sin(rockerAngle),
        0
      );

      const couplerEnd = joints.C;
      const footExtend = p.coupler_length * 0.8;
      const toCoupler = new THREE.Vector3().subVectors(couplerEnd, crankEnd).normalize();
      joints.D = new THREE.Vector3(
        couplerEnd.x + toCoupler.x * footExtend * 0.6,
        couplerEnd.y + toCoupler.y * footExtend * 0.6 - 50,
        0
      );
      footY = joints.D.y;
    } else {
      joints.C = new THREE.Vector3(-p.ground_link + p.rocker_length, 0, 0);
      joints.D = new THREE.Vector3(0, -100, 0);
      footY = joints.D.y;
    }

    return { joints, footY };
  }

  function _createLinkages() {
    linkages = [];

    const configs = [
      { x: -25, z: -50, rotY: 0, offset: 0, color: 0x8B4513 },
      { x: -25, z: 50, rotY: Math.PI, offset: 180, color: 0xA0522D },
      { x: 175, z: -50, rotY: 0, offset: 0, color: 0x8B4513 },
      { x: 175, z: 50, rotY: Math.PI, offset: 180, color: 0xA0522D }
    ];

    configs.forEach(cfg => {
      const group = new THREE.Group();
      group.position.set(cfg.x, 100, cfg.z);
      group.rotation.y = cfg.rotY;

      const rodA = _createRod(new THREE.Vector3(), new THREE.Vector3(), cfg.color, 3);
      const rodB = _createRod(new THREE.Vector3(), new THREE.Vector3(), cfg.color, 3);
      const rodC = _createRod(new THREE.Vector3(), new THREE.Vector3(), cfg.color, 3);
      const rodD = _createRod(new THREE.Vector3(), new THREE.Vector3(), cfg.color, 3);

      const pivotGeo = new THREE.SphereGeometry(5, 8, 8);
      const pivotMat = new THREE.MeshStandardMaterial({ color: 0xCD853F });
      const pivot = new THREE.Mesh(pivotGeo, pivotMat);

      const footGeo = new THREE.SphereGeometry(8, 12, 12);
      const footMat = new THREE.MeshStandardMaterial({ color: 0x333333 });
      const foot = new THREE.Mesh(footGeo, footMat);

      group.add(rodA, rodB, rodC, rodD, pivot, foot);
      scene.add(group);

      linkages.push({
        group,
        rods: [rodA, rodB, rodC, rodD],
        pivot,
        foot,
        offset: cfg.offset
      });
    });
  }

  function _updateLinkage(linkage, angle, offset = 0) {
    const actualAngle = (angle + offset) % 360;
    const { joints } = _solveJansenLinkage(actualAngle, params);

    const positions = [
      { from: joints.A, to: joints.B },
      { from: joints.B, to: joints.C },
      { from: joints.O, to: joints.C },
      { from: joints.C, to: joints.D }
    ];

    linkage.rods.forEach((rod, i) => {
      if (positions[i] && positions[i].from && positions[i].to) {
        const from = positions[i].from;
        const to = positions[i].to;
        rod.position.copy(from).add(to).multiplyScalar(0.5);
        const dir = new THREE.Vector3().subVectors(to, from);
        const len = dir.length();
        rod.scale.y = Math.max(0.01, len / 1);
        rod.geometry = new THREE.CylinderGeometry(3, 3, len || 1, 8);
        rod.quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0),
          dir.clone().normalize()
        );
      }
    });

    linkage.pivot.position.copy(joints.B || new THREE.Vector3());

    if (joints.D) {
      linkage.foot.position.copy(joints.D);
    }
  }

  function _createTrajectory() {
    const geometry = new THREE.BufferGeometry();
    const material = new THREE.LineBasicMaterial({ color: 0xFF6B6B, linewidth: 3 });
    trajectoryLine = new THREE.Line(geometry, material);
    scene.add(trajectoryLine);
    _updateTrajectory();
  }

  function _updateTrajectory() {
    if (!trajectoryLine) return;

    const points = [];
    for (let i = 0; i <= 360; i += 5) {
      const { joints } = _solveJansenLinkage(i, params);
      if (joints.D) {
        points.push(joints.D.x + 100, joints.D.y + 100, joints.D.z);
      }
    }

    const geometry = new THREE.BufferGeometry();
    const positionAttr = new THREE.Float32BufferAttribute(points, 3);
    geometry.setAttribute('position', positionAttr);
    trajectoryLine.geometry = geometry;
    trajectoryLine.visible = showTrajectory;
  }

  function _createGrid() {
    const grid = new THREE.GridHelper(2000, 40, 0x9CA3AF, 0x6B7280);
    grid.position.y = -5;
    scene.add(grid);
  }

  function _animate() {
    animationId = requestAnimationFrame(_animate);

    if (isPlaying) {
      const delta = 1 / 60;
      crankAngle = (crankAngle + delta * 30 * simulationSpeed) % 360;
      if (onAngleChange) onAngleChange(crankAngle);
    }

    if (bodyGroup) {
      bodyGroup.rotation.z = (bodyInclination * Math.PI) / 180;
    }

    if (showLinkages) {
      linkages.forEach(linkage => {
        linkage.group.visible = true;
        _updateLinkage(linkage, crankAngle, linkage.offset);
      });
    } else {
      linkages.forEach(linkage => {
        linkage.group.visible = false;
      });
    }

    if (trajectoryLine) {
      trajectoryLine.visible = showTrajectory;
    }

    if (controls) controls.update();
    renderer.render(scene, camera);
  }

  function setCrankAngle(angle) {
    crankAngle = ((angle % 360) + 360) % 360;
  }

  function getCrankAngle() {
    return crankAngle;
  }

  function setBodyInclination(angle) {
    bodyInclination = angle;
  }

  function setObstacleHeight(height) {
    obstacleHeight = height;
    _updateTerrain();
  }

  function setPlaying(playing) {
    isPlaying = playing;
  }

  function togglePlaying() {
    isPlaying = !isPlaying;
    return isPlaying;
  }

  function setSimulationSpeed(speed) {
    simulationSpeed = Math.max(0.1, Math.min(5.0, speed));
  }

  function setShowTrajectory(show) {
    showTrajectory = show;
    if (trajectoryLine) trajectoryLine.visible = show;
  }

  function setShowLinkages(show) {
    showLinkages = show;
  }

  function setParams(newParams) {
    params = { ...DEFAULT_PARAMS, ...newParams };
    _updateTrajectory();
  }

  function getFootPosition(angle) {
    const { joints } = _solveJansenLinkage(angle || crankAngle, params);
    return joints.D ? { x: joints.D.x, y: joints.D.y, z: joints.D.z } : null;
  }

  function generateFootTrajectory(start = 0, end = 360, samples = 72) {
    const trajectory = [];
    const step = (end - start) / samples;
    for (let i = 0; i <= samples; i++) {
      const angle = start + i * step;
      const { joints } = _solveJansenLinkage(angle, params);
      if (joints.D) {
        trajectory.push({ x: joints.D.x, y: joints.D.y, z: joints.D.z });
      }
    }
    return trajectory;
  }

  function dispose() {
    if (animationId) cancelAnimationFrame(animationId);
    if (renderer) renderer.dispose();
    if (scene) {
      while (scene.children.length > 0) {
        scene.remove(scene.children[0]);
      }
    }
    console.log('[WoodenOx3D] 资源已释放');
  }

  return {
    init,
    setCrankAngle,
    getCrankAngle,
    setBodyInclination,
    setObstacleHeight,
    setPlaying,
    togglePlaying,
    setSimulationSpeed,
    setShowTrajectory,
    setShowLinkages,
    setParams,
    getFootPosition,
    generateFootTrajectory,
    dispose
  };
})();
