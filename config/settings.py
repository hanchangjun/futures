"""
统一配置管理系统
支持从YAML文件、环境变量加载配置
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseSettings, Field, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings
import yaml

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# 确保目录存在
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


class ScorerConfig(PydanticBaseSettings):
    """信号评分配置"""
    weights: Dict[str, float] = {
        "structure": 20,
        "divergence": 20,
        "volume_price": 10,
        "time": 10,
        "position": 10,
        "sub_level": 10,
        "strength": 10,
        "confirmation": 10,
    }
    min_score: float = 60.0

    @validator('weights')
    def validate_weights(cls, v):
        """验证权重总和为100"""
        total = sum(v.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"权重总和应为100，当前为{total}")
        return v

    class Config:
        env_prefix = "SCORER_"


class FilterConfig(PydanticBaseSettings):
    """信号过滤配置"""
    # 强制检查
    check_structure_complete: bool = True
    check_position_clear: bool = True
    check_fractal_confirmation: bool = True

    # 排除条件
    major_news_window_minutes: int = 30
    low_liquidity_window_minutes: int = 30
    limit_move_percent: float = 2.0
    contract_switch_week: bool = True

    # 接受条件
    min_score: float = 70.0

    class Config:
        env_prefix = "FILTER_"


class DatabaseConfig(PydanticBaseSettings):
    """数据库配置"""
    url: str = "sqlite:///./data/futures.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    class Config:
        env_prefix = "DB_"


class TdxConfig(PydanticBaseSettings):
    """通达信配置"""
    servers: list = Field(
        default=[
            {"ip": "115.238.56.198", "port": 7709},
            {"ip": "115.238.90.165", "port": 7709},
            {"ip": "180.153.18.170", "port": 7709},
            {"ip": "119.147.212.81", "port": 7709},
        ]
    )
    pool_size: int = 3
    timeout: int = 10

    class Config:
        env_prefix = "TDX_"


class TianqinConfig(PydanticBaseSettings):
    """天勤配置"""
    username: Optional[str] = Field(default=None, env="TQ_USERNAME")
    password: Optional[str] = Field(default=None, env="TQ_PASSWORD")
    timeout: int = 10
    count: int = 5000

    class Config:
        env_prefix = "TQ_"


class LoggingConfig(PydanticBaseSettings):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: bool = True
    file_path: str = str(LOGS_DIR / "app.log")
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5

    class Config:
        env_prefix = "LOG_"


class AppConfig(PydanticBaseSettings):
    """应用总配置"""
    # 子配置
    scorer: ScorerConfig = ScorerConfig()
    filter: FilterConfig = FilterConfig()
    database: DatabaseConfig = DatabaseConfig()
    tdx: TdxConfig = TdxConfig()
    tianqin: TianqinConfig = TianqinConfig()
    logging: LoggingConfig = LoggingConfig()

    # 应用设置
    debug: bool = False
    environment: str = "production"  # development, production

    @classmethod
    def from_yaml(cls, yaml_path: Optional[Path] = None) -> "AppConfig":
        """从YAML文件加载配置"""
        if yaml_path is None:
            yaml_path = CONFIG_DIR / "config.yaml"

        if not yaml_path.exists():
            return cls()

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # 合并YAML配置到环境变量配置
        config = cls()

        if 'scorer' in data:
            config.scorer = ScorerConfig(**data['scorer'])
        if 'filter' in data:
            config.filter = FilterConfig(**data['filter'])

        return config

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
_settings: Optional[AppConfig] = None


def get_settings() -> AppConfig:
    """获取全局配置实例（单例）"""
    global _settings
    if _settings is None:
        _settings = AppConfig.from_yaml()
    return _settings


def reload_settings():
    """重新加载配置"""
    global _settings
    _settings = AppConfig.from_yaml()
    return _settings


# 便捷访问函数
def get_scorer_config() -> ScorerConfig:
    return get_settings().scorer


def get_filter_config() -> FilterConfig:
    return get_settings().filter


def get_db_config() -> DatabaseConfig:
    return get_settings().database


def get_tdx_config() -> TdxConfig:
    return get_settings().tdx


def get_tianqin_config() -> TianqinConfig:
    return get_settings().tianqin


def get_logging_config() -> LoggingConfig:
    return get_settings().logging
