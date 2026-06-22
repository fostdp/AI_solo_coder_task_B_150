import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parents[3]
_CONFIG_DIR = Path(os.getenv('CONFIG_DIR', str(_BASE_DIR / "config")))

_CACHED_CONFIGS: Dict[str, Dict[str, Any]] = {}


def get_config_path(config_name: str) -> Path:
    if not config_name.endswith('.json'):
        config_name += '.json'
    return _CONFIG_DIR / config_name


def load_config(config_name: str, force_reload: bool = False) -> Optional[Dict[str, Any]]:
    global _CACHED_CONFIGS

    if config_name in _CACHED_CONFIGS and not force_reload:
        return _CACHED_CONFIGS[config_name]

    search_paths = [
        get_config_path(config_name),
        _BASE_DIR / "config" / f"{config_name}.json",
        Path(__file__).resolve().parents[2] / "config" / f"{config_name}.json",
        Path.cwd() / "config" / f"{config_name}.json",
    ]

    config_path = None
    for p in search_paths:
        if p.exists():
            config_path = p
            break

    if config_path is None:
        logger.error(f"无法找到配置文件: {config_name}, 搜索路径: {[str(p) for p in search_paths]}")
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        _CACHED_CONFIGS[config_name] = config
        logger.info(f"配置文件加载成功: {config_path}")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"配置文件JSON解析失败: {config_path}, 错误: {e}")
        return None
    except Exception as e:
        logger.error(f"加载配置文件失败: {config_path}, 错误: {e}")
        return None


def get_nested_config(config: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def reload_all_configs():
    global _CACHED_CONFIGS
    _CACHED_CONFIGS.clear()
    logger.info("所有配置缓存已清除")


def get_mechanism_config() -> Dict[str, Any]:
    return load_config('mechanism_params') or {}


def get_terrain_config() -> Dict[str, Any]:
    return load_config('terrain_params') or {}
