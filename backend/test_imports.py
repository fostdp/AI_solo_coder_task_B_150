import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("Testing imports...")
try:
    from app.dynamics_worker import AsyncMultibodyDynamics, DynamicsWorkerClient, start_dynamics_worker, stop_dynamics_worker
    print("✓ All imports successful!")
    print(f"  AsyncMultibodyDynamics: {AsyncMultibodyDynamics}")
    print(f"  DynamicsWorkerClient: {DynamicsWorkerClient}")
    print(f"  start_dynamics_worker: {start_dynamics_worker}")
    print(f"  stop_dynamics_worker: {stop_dynamics_worker}")
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTesting submodule imports...")
try:
    from app.dynamics_worker.messages import (
        DYNAMICS_REQUEST_CHANNEL,
        DYNAMICS_RESPONSE_PREFIX,
        DynamicsRequest,
        DynamicsResponse,
        serialize_point,
        deserialize_point,
    )
    print("✓ messages.py imports successful!")
    print(f"  DYNAMICS_REQUEST_CHANNEL: {DYNAMICS_REQUEST_CHANNEL}")
    print(f"  DYNAMICS_RESPONSE_PREFIX: {DYNAMICS_RESPONSE_PREFIX}")
except Exception as e:
    print(f"✗ messages.py import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll tests passed!")
