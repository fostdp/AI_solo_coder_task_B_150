export interface Point3D {
  x: number
  y: number
  z: number
}

export interface IKJoint {
  position: Point3D
  length: number
  minAngle?: number
  maxAngle?: number
}

export interface IKChain {
  joints: IKJoint[]
  target: Point3D
  base: Point3D
}

export interface IKSolution {
  joints: Point3D[]
  angles: number[]
  distanceToTarget: number
  iterations: number
  converged: boolean
}

export interface IKConfig {
  maxIterations?: number
  tolerance?: number
  enableJointLimits?: boolean
}

export class FabrikSolver {
  private maxIterations: number
  private tolerance: number
  private enableJointLimits: boolean

  constructor(config: IKConfig = {}) {
    this.maxIterations = config.maxIterations ?? 20
    this.tolerance = config.tolerance ?? 0.1
    this.enableJointLimits = config.enableJointLimits ?? true
  }

  private subtract(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.x - b.x,
      y: a.y - b.y,
      z: a.z - b.z
    }
  }

  private add(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.x + b.x,
      y: a.y + b.y,
      z: a.z + b.z
    }
  }

  private multiply(v: Point3D, scalar: number): Point3D {
    return {
      x: v.x * scalar,
      y: v.y * scalar,
      z: v.z * scalar
    }
  }

  private distance(a: Point3D, b: Point3D): number {
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dz = b.z - a.z
    return Math.sqrt(dx * dx + dy * dy + dz * dz)
  }

  private normalize(v: Point3D): Point3D {
    const len = Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if (len < 0.0001) return { x: 0, y: 0, z: 0 }
    return {
      x: v.x / len,
      y: v.y / len,
      z: v.z / len
    }
  }

  private dot(a: Point3D, b: Point3D): number {
    return a.x * b.x + a.y * b.y + a.z * b.z
  }

  private clampAngle(
    joint: IKJoint,
    prevJoint: Point3D,
    nextJoint: Point3D,
    parentDirection: Point3D
  ): Point3D {
    if (!this.enableJointLimits || (joint.minAngle === undefined && joint.maxAngle === undefined)) {
      return nextJoint
    }

    const toNext = this.normalize(this.subtract(nextJoint, prevJoint))
    const toParent = this.normalize(this.subtract(parentDirection, prevJoint))

    let angle = Math.acos(Math.max(-1, Math.min(1, this.dot(toNext, toParent))))
    let crossProduct = this.cross(toParent, toNext)

    const minAngle = joint.minAngle ?? -180
    const maxAngle = joint.maxAngle ?? 180
    const minRad = (minAngle * Math.PI) / 180
    const maxRad = (maxAngle * Math.PI) / 180

    if (angle > maxRad) {
      const axis = this.normalize(crossProduct)
      const rotation = maxRad
      return this.rotateVectorAroundAxis(toNext, axis, rotation - maxRad)
    } else if (angle < minRad) {
      const axis = this.normalize(crossProduct)
      return this.rotateVectorAroundAxis(toNext, axis, minRad - angle)
    }

    return nextJoint
  }

  private cross(a: Point3D, b: Point3D): Point3D {
    return {
      x: a.y * b.z - a.z * b.y,
      y: a.z * b.x - a.x * b.z,
      z: a.x * b.y - a.y * b.x
    }
  }

  private rotateVectorAroundAxis(
    v: Point3D,
    axis: Point3D,
    angle: number
  ): Point3D {
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    const t = 1 - cos

    const { x, y, z } = axis

    const rotationMatrix = [
      [t * x * x + cos, t * x * y - sin * z, t * x * z + sin * y],
      [t * x * y + sin * z, t * y * y + cos, t * y * z - sin * x],
      [t * x * z - sin * y, t * y * z + sin * x, t * z * z + cos]
    ]

    return {
      x: rotationMatrix[0][0] * v.x + rotationMatrix[0][1] * v.y + rotationMatrix[0][2] * v.z,
      y: rotationMatrix[1][0] * v.x + rotationMatrix[1][1] * v.y + rotationMatrix[1][2] * v.z,
      z: rotationMatrix[2][0] * v.x + rotationMatrix[2][1] * v.y + rotationMatrix[2][2] * v.z
    }
  }

  private calculateJointAngles(joints: Point3D[]): number[] {
    const angles: number[] = []

    for (let i = 0; i < joints.length - 2; i++) {
      if (i === 0) {
        angles.push(0)
        continue
      }

      const prev = joints[i - 1]
      const curr = joints[i]
      const next = joints[i + 1]

      const v1 = this.subtract(prev, curr)
      const v2 = this.subtract(next, curr)

      const dot = this.dot(v1, v2)
      const len1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y + v1.z * v1.z)
      const len2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y + v2.z * v2.z)

      if (len1 > 0.0001 && len2 > 0.0001) {
        const cosAngle = dot / (len1 * len2)
        const angle = Math.acos(Math.max(-1, Math.min(1, cosAngle)))
        angles.push((angle * 180) / Math.PI)
      } else {
        angles.push(0)
      }
    }

    if (joints.length > 2) {
      angles.push(0)
    }

    return angles
  }

  public solve(
    chain: IKChain,
    debugCallback?: (iteration: number, joints: Point3D[]) => void
  ): IKSolution {
    const { joints, target, base } = chain
    const n = joints.length
    const lengths = joints.map(j => j.length)

    let positions: Point3D[] = joints.map(j => ({ ...j.position }))

    const totalLength = lengths.reduce((sum, len) => sum + len, 0)
    const distToTarget = this.distance(base, target)

    if (distToTarget > totalLength) {
      const direction = this.normalize(this.subtract(target, base))
      let currentPos = { ...base }
      positions[0] = { ...currentPos }

      for (let i = 1; i < n; i++) {
        const dir = this.normalize(this.subtract(target, currentPos))
        currentPos = this.add(currentPos, this.multiply(dir, lengths[i - 1]))
        positions[i] = { ...currentPos }
      }

      return {
        joints: positions,
        angles: this.calculateJointAngles(positions),
        distanceToTarget: this.distance(positions[n - 1], target),
        iterations: 0,
        converged: false
      }
    }

    let iteration = 0
    let lastDistance = Infinity

    while (iteration < this.maxIterations) {
      const startDistance = this.distance(positions[n - 1], target)

      positions[n - 1] = { ...target }

      for (let i = n - 2; i >= 0; i--) {
        const direction = this.normalize(this.subtract(positions[i], positions[i + 1]))
        positions[i] = this.add(positions[i + 1], this.multiply(direction, lengths[i]))
      }

      positions[0] = { ...base }

      for (let i = 1; i < n - 1; i++) {
        const direction = this.normalize(this.subtract(positions[i + 1], positions[i]))
        positions[i + 1] = this.add(positions[i], this.multiply(direction, lengths[i]))

        if (this.enableJointLimits && joints[i].minAngle !== undefined && joints[i].maxAngle !== undefined) {
          const parentDir = i > 0 ? positions[i - 1] : base
          positions[i] = this.clampAngle(joints[i], positions[i - 1], positions[i], parentDir)
        }
      }

      const endDistance = this.distance(positions[n - 1], target)

      if (debugCallback) {
        debugCallback(iteration + 1, positions)
      }

      if (Math.abs(startDistance - endDistance) < this.tolerance) {
        break
      }

      lastDistance = endDistance
      iteration++
    }

    return {
      joints: positions,
      angles: this.calculateJointAngles(positions),
      distanceToTarget: this.distance(positions[n - 1], target),
      iterations: iteration + 1,
      converged: iteration < this.maxIterations - 1
    }
  }

  public solveForJansenLinkage(
    target: Point3D,
    base: Point3D,
    params: {
      crankLength: number
      rockerLength: number
      couplerLength: number
      groundLink: number
    },
    currentCrankAngle: number = 0
  ): IKSolution {
    const joints: IKJoint[] = [
      {
      position: { ...base },
      length: params.crankLength,
      minAngle: -180,
      maxAngle: 180
    },
    {
      position: {
        x: base.x + params.crankLength,
        y: base.y,
        z: base.z
      },
      length: params.couplerLength,
      minAngle: -90,
      maxAngle: 90
    },
    {
      position: {
        x: base.x + params.groundLink,
        y: base.y,
        z: base.z
      },
      length: params.rockerLength,
      minAngle: -60,
      maxAngle: 60
    },
    {
      position: {
        x: base.x + params.groundLink + params.rockerLength,
        y: base.y,
        z: base.z
      },
      length: 0
    }
    ]

    return this.solve({ joints, target, base })
  }

  public createDebugVisualizationData(
    solution: IKSolution,
    originalJoints: Point3D[],
    target: Point3D,
    base: Point3D
  ) {
    const lines: { start: Point3D; end: Point3D; color: string }[] = []
    const points: { position: Point3D; color: string; size: number }[] = []

    for (let i = 0; i < solution.joints.length - 1; i++) {
      lines.push({
        start: solution.joints[i],
        end: solution.joints[i + 1],
        color: i % 2 === 0 ? '#B8860B' : '#DAA520'
      })
    }

    solution.joints.forEach((joint, index) => {
      points.push({
        position: joint,
        color: index === 0 ? '#00FF00' : index === solution.joints.length - 1 ? '#FF0000' : '#FFD700',
        size: index === 0 ? 8 : index === solution.joints.length - 1 ? 8 : 5
      })
    })

    points.push({
      position: target,
      color: '#00FFFF',
      size: 10
    })

    points.push({
      position: base,
      color: '#FF00FF',
      size: 10
    })

    lines.push({
      start: solution.joints[solution.joints.length - 1],
      end: target,
      color: solution.converged ? '#00FF00' : '#FF0000'
    })

    return { lines, points }
  }
}

export class IKDebugger {
  private solver: FabrikSolver
  private history: { iteration: number; joints: Point3D[]; distance: number }[] = []

  constructor(config: IKConfig = {}) {
    this.solver = new FabrikSolver(config)
  }

  public solveWithDebug(chain: IKChain): IKSolution & { history: typeof this.history } {
    this.history = []

    const solution = this.solver.solve(chain, (iteration, joints) => {
      const distance = this.solver.distance(
        joints[joints.length - 1],
        chain.target
      )
      this.history.push({ iteration, joints: [...joints], distance })
    })

    return { ...solution, history: [...this.history] }
  }

  public getConvergencePlot(): { iteration: number; distance: number }[] {
    return this.history.map(h => ({ iteration: h.iteration, distance: h.distance }))
  }

  public getErrorMetrics() {
    if (this.history.length === 0) return null

    const first = this.history[0].distance
    const last = this.history[this.history.length - 1].distance
    const improvement = first > 0 ? (first - last) / first : 0

    return {
      initialError: first,
      finalError: last,
      improvement: improvement * 100,
      iterations: this.history.length
    }
  }
}
