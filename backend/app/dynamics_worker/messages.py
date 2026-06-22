import time
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass, field, asdict


DYNAMICS_REQUEST_CHANNEL = 'dynamics:request'
DYNAMICS_RESPONSE_PREFIX = 'dynamics:response'


@dataclass
class DynamicsRequest:
    id: str
    method: str
    params: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'DynamicsRequest':
        data = json.loads(json_str)
        return cls(**data)

    def response_channel(self) -> str:
        return f'{DYNAMICS_RESPONSE_PREFIX}:{self.id}'


@dataclass
class DynamicsResponse:
    id: str
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'DynamicsResponse':
        data = json.loads(json_str)
        return cls(**data)


def serialize_point(obj: Any) -> Any:
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    elif hasattr(obj, '__dict__'):
        return {
            k: serialize_point(v)
            for k, v in obj.__dict__.items()
            if not k.startswith('_')
        }
    elif isinstance(obj, dict):
        return {k: serialize_point(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_point(item) for item in obj]
    return obj


def deserialize_point(data: Any, target_type: Any = None) -> Any:
    from app.models.schemas import Point3D, Point2D

    if isinstance(data, dict):
        if target_type == Point3D and all(k in data for k in ('x', 'y', 'z')):
            return Point3D(**{k: float(v) for k, v in data.items()})
        elif target_type == Point2D and all(k in data for k in ('x', 'y')):
            return Point2D(**{k: float(v) for k, v in data.items()})
        elif target_type is None:
            if all(k in data for k in ('x', 'y', 'z')):
                return Point3D(**{k: float(v) for k, v in data.items()})
            elif all(k in data for k in ('x', 'y')):
                return Point2D(**{k: float(v) for k, v in data.items()})
        return {k: deserialize_point(v, None) for k, v in data.items()}
    elif isinstance(data, list):
        return [deserialize_point(item, None) for item in data]
    return data


def deserialize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    from app.models.schemas import Point3D, Point2D

    result = {}
    for key, value in params.items():
        if key in ('joints', 'com_positions', 'forces') and isinstance(value, dict):
            result[key] = deserialize_dict_of_points(value)
        elif key in ('payload_offset', 'com', 'ground_reaction', 'zmp', 'current_com', 'target_com'):
            result[key] = deserialize_point(value)
        elif key in ('support_polygon',) and isinstance(value, list):
            result[key] = [deserialize_point(item, Point2D) for item in value]
        else:
            result[key] = value
    return result


def deserialize_dict_of_points(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for key, value in data.items():
        result[key] = deserialize_point(value)
    return result
