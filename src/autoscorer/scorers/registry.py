"""
Scorer注册表系统，支持静态注册和动态热注册
"""
import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Type, Optional, Any, List
import inspect
import logging

logger = logging.getLogger(__name__)

class ScorerRegistry:
    """Scorer注册表，支持静态和动态注册，线程安全"""
    
    def __init__(self):
        self._scorers: Dict[str, Type] = {}
        self._loaded_files: Dict[str, float] = {}  # 文件路径 -> 修改时间
        self._lock = threading.RLock()  # 线程安全锁
        self._watchers: Dict[str, threading.Thread] = {}  # 文件监控线程
        self._watch_enabled = True
    
    def register(self, name: str, scorer_class: Type) -> None:
        """注册scorer类"""
        if not hasattr(scorer_class, 'score'):
            raise ValueError(f"Scorer class {scorer_class.__name__} must have a 'score' method")
        
        with self._lock:
            old_class = self._scorers.get(name)
            self._scorers[name] = scorer_class
            
            if old_class != scorer_class:
                logger.info(f"Registered scorer: {name} -> {scorer_class.__name__}")
                if old_class:
                    logger.info(f"Replaced existing scorer: {name}")
    
    def get(self, name: str) -> Optional[Type]:
        """获取scorer类"""
        with self._lock:
            return self._scorers.get(name)
    
    def get_instance(self, name: str):
        """获取scorer实例（兼容旧API）"""
        scorer_cls = self.get(name)
        if scorer_cls is None:
            raise KeyError(f"scorer '{name}' not found")
        return scorer_cls()
    
    def list_scorers(self) -> Dict[str, str]:
        """列出所有已注册的scorer"""
        with self._lock:
            return {name: cls.__name__ for name, cls in self._scorers.items()}
    
    def unregister(self, name: str) -> bool:
        """注销scorer"""
        with self._lock:
            if name in self._scorers:
                del self._scorers[name]
                logger.info(f"Unregistered scorer: {name}")
                return True
            return False
    
    def clear(self) -> None:
        """清空所有scorer"""
        with self._lock:
            self._scorers.clear()
            logger.info("Cleared all scorers")
    
    def load_from_file(self, file_path: str, force_reload: bool = False) -> Dict[str, Type]:
        """从Python文件动态加载scorer
        
        Args:
            file_path: Python文件路径
            force_reload: 是否强制重新加载
            
        Returns:
            加载的scorer字典 {name: class}
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Scorer file not found: {file_path}")
        
        if not path.suffix == '.py':
            raise ValueError(f"File must be a Python file: {file_path}")
        
        # 检查文件是否需要重新加载
        current_mtime = path.stat().st_mtime
        if not force_reload and file_path in self._loaded_files:
            if self._loaded_files[file_path] >= current_mtime:
                logger.debug(f"Scorer file {file_path} already loaded and not modified")
                return {}
        
        # 动态加载模块
        module_name = f"dynamic_scorer_{path.stem}_{int(current_mtime)}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        
        # 如果模块已存在，先移除
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        try:
            spec.loader.exec_module(module)
            sys.modules[module_name] = module
        except Exception as e:
            raise ImportError(f"Failed to execute module {file_path}: {e}")
        
        # 查找scorer类
        loaded_scorers = {}
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                hasattr(obj, 'score') and 
                obj.__module__ == module_name and
                not name.startswith('_')):
                
                # 自动注册找到的scorer类
                scorer_name = getattr(obj, 'SCORER_NAME', name.lower())
                self.register(scorer_name, obj)
                loaded_scorers[scorer_name] = obj
                logger.info(f"Auto-registered scorer from {file_path}: {scorer_name}")
        
        self._loaded_files[file_path] = current_mtime
        return loaded_scorers
    
    def load_from_directory(self, dir_path: str, pattern: str = "*.py") -> Dict[str, Type]:
        """从目录批量加载scorer文件
        
        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式
            
        Returns:
            加载的scorer字典
        """
        directory = Path(dir_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        loaded_scorers = {}
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                try:
                    file_scorers = self.load_from_file(str(file_path))
                    loaded_scorers.update(file_scorers)
                except Exception as e:
                    logger.error(f"Failed to load scorer from {file_path}: {e}")
        
        return loaded_scorers
    
    def reload_file(self, file_path: str) -> Dict[str, Type]:
        """重新加载指定文件的scorer"""
        return self.load_from_file(file_path, force_reload=True)
    
    def start_watching(self, file_path: str, check_interval: float = 1.0) -> None:
        """开始监控文件变化并自动重新加载"""
        if not self._watch_enabled:
            return
            
        if file_path in self._watchers:
            logger.warning(f"Already watching file: {file_path}")
            return
        
        def watch_file():
            logger.info(f"Started watching file: {file_path}")
            last_mtime = 0
            
            while self._watch_enabled and file_path in self._watchers:
                try:
                    path = Path(file_path)
                    if path.exists():
                        current_mtime = path.stat().st_mtime
                        if current_mtime > last_mtime:
                            if last_mtime > 0:  # 不在首次检查时重新加载
                                logger.info(f"File changed, reloading: {file_path}")
                                try:
                                    self.reload_file(file_path)
                                except Exception as e:
                                    logger.error(f"Failed to reload {file_path}: {e}")
                            last_mtime = current_mtime
                    
                    time.sleep(check_interval)
                except Exception as e:
                    logger.error(f"Error watching file {file_path}: {e}")
                    time.sleep(check_interval)
        
        thread = threading.Thread(target=watch_file, daemon=True)
        self._watchers[file_path] = thread
        thread.start()
    
    def stop_watching(self, file_path: str) -> bool:
        """停止监控指定文件"""
        if file_path in self._watchers:
            del self._watchers[file_path]
            logger.info(f"Stopped watching file: {file_path}")
            return True
        return False
    
    def stop_all_watching(self) -> None:
        """停止所有文件监控"""
        self._watch_enabled = False
        self._watchers.clear()
        logger.info("Stopped all file watching")
    
    def get_watched_files(self) -> List[str]:
        """获取正在监控的文件列表"""
        return list(self._watchers.keys())

# 全局注册表实例
_registry = ScorerRegistry()

def register(name: str):
    """装饰器：注册scorer类"""
    def decorator(cls):
        _registry.register(name, cls)
        return cls
    return decorator

def get_scorer(name: str):
    """获取scorer实例"""
    return _registry.get_instance(name)

def get_scorer_class(name: str) -> Optional[Type]:
    """获取scorer类"""
    return _registry.get(name)

def list_scorers() -> Dict[str, str]:
    """列出所有scorer"""
    return _registry.list_scorers()

def load_scorer_file(file_path: str, force_reload: bool = False) -> Dict[str, Type]:
    """加载scorer文件"""
    return _registry.load_from_file(file_path, force_reload)

def load_scorer_directory(dir_path: str, pattern: str = "*.py") -> Dict[str, Type]:
    """从目录加载scorer文件"""
    return _registry.load_from_directory(dir_path, pattern)

def reload_scorer_file(file_path: str) -> Dict[str, Type]:
    """重新加载scorer文件"""
    return _registry.reload_file(file_path)

def start_watching_file(file_path: str, check_interval: float = 1.0) -> None:
    """开始监控文件变化"""
    _registry.start_watching(file_path, check_interval)

def stop_watching_file(file_path: str) -> bool:
    """停止监控文件"""
    return _registry.stop_watching(file_path)

def get_watched_files() -> List[str]:
    """获取监控的文件列表"""
    return _registry.get_watched_files()

def get_scorer_registry() -> Dict[str, Type]:
    """获取所有已注册的评分器类（兼容旧API）"""
    return _registry._scorers.copy()

# 获取全局注册表实例，用于API管理
def get_registry() -> ScorerRegistry:
    """获取全局注册表实例"""
    return _registry
