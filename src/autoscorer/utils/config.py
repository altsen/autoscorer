import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class Config:
    """配置管理类，支持YAML文件和环境变量覆盖"""
    
    def __init__(self, path: str = "config.yaml"):
        self.path = Path(path)
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 智能查找配置文件路径
        config_path = self._find_config_file()
        
        if config_path is None:
            logger.warning(f"Config file not found: {self.path}, using defaults")
            self.data = {}
            return
        
        self.path = config_path
        
        try:
            self.data = yaml.safe_load(self.path.read_text(encoding='utf-8'))
            if self.data is None:
                self.data = {}
            logger.info(f"Loaded config from: {self.path}")
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {self.path}: {e}")
            self.data = {}
        except Exception as e:
            logger.error(f"Error loading config {self.path}: {e}")
            self.data = {}
    
    def _find_config_file(self) -> Optional[Path]:
        """智能查找配置文件路径"""
        # 1. 如果指定的路径是绝对路径，直接使用
        if self.path.is_absolute():
            if self.path.exists():
                return self.path
            else:
                return None
        
        # 2. 如果指定的路径是相对路径，先检查当前工作目录
        cwd_path = Path.cwd() / self.path
        if cwd_path.exists():
            return cwd_path
        
        # 3. 检查项目根目录（从源代码目录向上查找）
        project_root = Path(__file__).resolve().parents[3]
        project_config = project_root / self.path.name
        if project_config.exists():
            return project_config
        
        # 4. 检查用户主目录
        home_config = Path.home() / f".autoscorer/{self.path.name}"
        if home_config.exists():
            return home_config
        
        # 5. 检查系统配置目录
        system_config = Path("/etc/autoscorer") / self.path.name
        if system_config.exists():
            return system_config
        
        return None
    
    def get_config_path(self) -> str:
        """获取当前使用的配置文件路径"""
        return str(self.path)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，环境变量优先级高于配置文件"""
        # 环境变量覆盖
        if key in os.environ:
            env_value = os.environ[key]
            # 尝试类型转换
            return self._convert_env_value(env_value, default)
        return self.data.get(key, default)
    
    def get_nested(self, *keys, default: Any = None) -> Any:
        """获取嵌套配置值"""
        cur = self.data
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur
    
    def _convert_env_value(self, value: str, default: Any) -> Any:
        """转换环境变量值到适当类型"""
        if default is None:
            return value
        
        # 根据默认值类型推断
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return value
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return value
        elif isinstance(default, list):
            # 支持逗号分隔的列表
            return [item.strip() for item in value.split(',') if item.strip()]
        
        return value
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        
        # Docker配置验证
        docker_host = self.get("DOCKER_HOST")
        if docker_host and not (docker_host.startswith("unix://") or docker_host.startswith("tcp://")):
            errors.append("DOCKER_HOST must start with unix:// or tcp://")
        
        # 资源配置验证
        try:
            cpu = self.get("DEFAULT_CPU", 1)
            if not isinstance(cpu, (int, float)) or cpu <= 0:
                errors.append("DEFAULT_CPU must be a positive number")
        except Exception:
            errors.append("DEFAULT_CPU invalid format")
        
        # 内存格式验证
        memory = self.get("DEFAULT_MEMORY", "4g")
        if not self._validate_memory_format(str(memory)):
            errors.append(f"DEFAULT_MEMORY invalid format: {memory}")
        
        # GPU配置验证
        try:
            gpu = self.get("DEFAULT_GPU", 0)
            if not isinstance(gpu, int) or gpu < 0:
                errors.append("DEFAULT_GPU must be a non-negative integer")
        except Exception:
            errors.append("DEFAULT_GPU invalid format")
        
        # 超时验证
        try:
            timeout = self.get("TIMEOUT", 1800)
            if not isinstance(timeout, int) or timeout <= 0:
                errors.append("TIMEOUT must be a positive integer")
        except Exception:
            errors.append("TIMEOUT invalid format")
        
        # K8s配置验证（如果启用）
        if self.get("K8S_ENABLED", False):
            k8s_api = self.get("K8S_API")
            if not k8s_api:
                errors.append("K8S_API is required when K8S_ENABLED=true")
            elif not k8s_api.startswith("https://"):
                errors.append("K8S_API must be an HTTPS URL")
            
            if not self.get("K8S_NAMESPACE"):
                errors.append("K8S_NAMESPACE is required when K8S_ENABLED=true")
        
        return errors
    
    def _validate_memory_format(self, memory_str: str) -> bool:
        """验证内存格式是否合法 (例如: 1Gi, 512Mi, 2g, 1024m)"""
        import re
        pattern = r'^\d+(\.\d+)?[gGmM]i?$'
        return bool(re.match(pattern, memory_str.strip()))
    
    def dump(self) -> Dict[str, Any]:
        """导出当前配置（隐藏敏感信息）"""
        sensitive_keys = {"REGISTRY_PASS", "K8S_TOKEN", "CELERY_BROKER", "CELERY_BACKEND"}
        result = {}
        for key, value in self.data.items():
            if key in sensitive_keys:
                result[key] = "***" if value else None
            else:
                result[key] = value
        return result


# 静态方法用于配置文件路径查找
def get_config_search_paths(config_name: str = "config.yaml") -> List[str]:
    """获取配置文件的搜索路径列表"""
    paths = []
    
    # 1. 当前工作目录
    paths.append(str(Path.cwd() / config_name))
    
    # 2. 项目根目录
    project_root = Path(__file__).resolve().parents[3]
    paths.append(str(project_root / config_name))
    
    # 3. 用户主目录
    paths.append(str(Path.home() / f".autoscorer/{config_name}"))
    
    # 4. 系统配置目录
    paths.append(f"/etc/autoscorer/{config_name}")
    
    return paths


def find_config_file(config_name: str = "config.yaml") -> Optional[str]:
    """查找配置文件，返回第一个存在的路径"""
    for path_str in get_config_search_paths(config_name):
        path = Path(path_str)
        if path.exists():
            return str(path)
    return None


# 全局配置实例
_global_config: Optional[Config] = None


def get_config(config_path: str = "config.yaml") -> Config:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config


# 用法：
# cfg = Config()
# cfg.get("DOCKER_HOST")
# cfg.get_nested("K8S_DEFAULT_RESOURCES", "cpu")
# errors = cfg.validate()
# config_dump = cfg.dump()
