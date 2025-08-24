# AutoScorer 算法开发标准

基于AutoScorer v2.0评分系统的算法开发规范，支持动态注册、热重载和模块化开发。

## 架构概览

AutoScorer采用现代化的评分器架构，支持插件式算法开发：

```
src/autoscorer/scorers/
├── __init__.py           # 包初始化
├── registry.py           # 动态注册和热重载系统
├── base_csv.py          # CSV数据处理基类
├── classification.py    # 分类任务评分器
├── regression.py        # 回归任务评分器
├── detection.py         # 检测任务评分器
└── custom_scorers/      # 自定义评分器目录 (支持热重载)
    ├── example_scorers.py
    └── hot_reload_test.py
```

## 核心特性

- 🔧 **动态注册**: 基于装饰器的自动注册机制
- 🔥 **热重载**: 文件变化监控和自动重新加载
- 📦 **模块化**: 支持分类、回归、检测等任务类型
- 🛠️ **标准化**: 统一的接口和错误处理
- 🧪 **扩展性**: 支持第三方算法即插即用

## 评分器注册系统

### 动态注册机制

AutoScorer使用基于装饰器的动态注册系统，支持运行时发现和管理评分器：

```python
from autoscorer.scorers.registry import register, ScorerRegistry

# 全局注册表
registry = ScorerRegistry()

# 注册装饰器
@register("my_scorer")
class MyScorer:
    name = "my_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 评分逻辑实现
        pass
```

### 注册表功能

**核心API:**

```python
from autoscorer.scorers.registry import (
    register,           # 注册装饰器
    get_scorer,         # 获取评分器实例
    get_scorer_class,   # 获取评分器类
    list_scorers,       # 列出所有评分器
    load_scorer_file,   # 加载文件中的评分器
    start_watching_file # 开始文件监控
)

# 使用示例
@register("custom_f1")
class CustomF1Scorer:
    name = "custom_f1"
    version = "1.0.0"
    
    def score(self, workspace, params):
        return Result(...)

# 获取和使用
scorer = get_scorer("custom_f1")
result = scorer.score(workspace_path, {})
```

### 线程安全设计

注册表采用线程安全设计，支持并发环境：

```python
class ScorerRegistry:
    def __init__(self):
        self._scorers = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, scorer_class: type):
        """线程安全的注册操作"""
        with self._lock:
            self._scorers[name] = scorer_class
    
    def get(self, name: str):
        """线程安全的获取操作"""
        with self._lock:
            return self._scorers.get(name)
```

## 热重载系统

### 文件监控机制

AutoScorer支持自动监控文件变化并热重载评分器：

```python
from autoscorer.scorers.registry import start_watching_file, stop_watching_file

# 开始监控文件
start_watching_file("custom_scorers/my_scorer.py", check_interval=1.0)

# 当文件修改时，系统自动重新加载评分器
# 无需重启服务即可使用新的评分器版本
```

### 监控实现原理

```python
def start_watching(self, file_path: str, check_interval: float = 1.0):
    """开始监控文件变化并自动重新加载"""
    def watch_file():
        last_mtime = 0
        while self._watch_enabled and file_path in self._watchers:
            try:
                path = Path(file_path)
                if path.exists():
                    current_mtime = path.stat().st_mtime
                    if current_mtime > last_mtime:
                        if last_mtime > 0:  # 不在首次检查时重新加载
                            logger.info(f"File changed, reloading: {file_path}")
                            self.reload_file(file_path)
                        last_mtime = current_mtime
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error watching file {file_path}: {e}")
    
    thread = threading.Thread(target=watch_file, daemon=True)
    self._watchers[file_path] = thread
    thread.start()
```

### 热重载API使用

```python
from autoscorer.scorers.registry import (
    load_scorer_file, 
    reload_scorer_file,
    start_watching_file,
    stop_watching_file,
    get_watched_files
)

# 1. 加载评分器文件
loaded_scorers = load_scorer_file("custom_scorers/my_scorer.py")
print(f"Loaded scorers: {list(loaded_scorers.keys())}")

# 2. 开启自动监控
start_watching_file("custom_scorers/my_scorer.py")

# 3. 手动重新加载
reloaded_scorers = reload_scorer_file("custom_scorers/my_scorer.py")

# 4. 查看监控状态
watched_files = get_watched_files()
print(f"Watching files: {watched_files}")

# 5. 停止监控
stop_watching_file("custom_scorers/my_scorer.py")
```

### Web API集成

热重载功能完全集成到Web API中：

```bash
# 列出所有评分器
curl http://localhost:8000/scorers

# 加载评分器文件并启用监控
curl -X POST http://localhost:8000/scorers/load \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py", "auto_watch": true}'

# 手动重新加载
curl -X POST http://localhost:8000/scorers/reload \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py"}'

# 开始监控文件
curl -X POST http://localhost:8000/scorers/watch \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py", "check_interval": 1.0}'

# 停止监控
curl -X DELETE "http://localhost:8000/scorers/watch?file_path=custom_scorers/my_scorer.py"

# 查看监控状态
curl http://localhost:8000/scorers/watch
```

## 评分器开发标准

### 核心接口定义

所有评分器必须包含以下属性和方法：

```python
from pathlib import Path
from typing import Dict
from autoscorer.schemas.result import Result

class ScorerInterface:
    name: str          # 评分器唯一标识符
    version: str       # 版本号
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """
        评分主入口
        Args:
            workspace: 工作区路径
            params: 评分参数
        Returns:
            Result: 标准化结果对象
        """
        pass
```

### 评分器实现模板

```python
from __future__ import annotations
from pathlib import Path
from typing import Dict
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("my_algorithm")  # 注册到系统
class MyAlgorithm(BaseCSVScorer):  # 可选：继承BaseCSVScorer获得CSV处理能力
    name = "my_algorithm"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """算法评分实现"""
        try:
            # 1. 数据加载和验证
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            
            # 2. 数据一致性校验
            self._validate_data_consistency(gt_data, pred_data)
            
            # 3. 计算指标
            metrics = self._compute_metrics(gt_data, pred_data)
            
            # 4. 返回标准化结果
            return Result(
                summary={"score": metrics["main_metric"]},
                metrics=metrics,
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name, 
                    "version": self.version,
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"Algorithm {self.name} failed: {str(e)}",
                details={"algorithm": self.name, "version": self.version}
            )
    
    def _load_ground_truth(self, workspace: Path):
        """加载标准答案，算法特定实现"""
        gt_path = workspace / "input" / "gt.csv"
        return self._load_and_validate_csv(gt_path, ["id", "label"])
    
    def _load_predictions(self, workspace: Path):
        """加载模型预测，算法特定实现"""
        pred_path = workspace / "output" / "pred.csv"
        return self._load_and_validate_csv(pred_path, ["id", "label"])
    
    def _validate_data_consistency(self, gt_data, pred_data):
        """数据一致性校验"""
        self._validate_id_consistency(gt_data, pred_data)
        # 添加算法特定的校验逻辑...
    
    def _compute_metrics(self, gt_data, pred_data):
        """计算评分指标，算法核心逻辑"""
        # 算法特定的计算逻辑
        return {"main_metric": 0.85}
```

### 热重载兼容性

为了支持热重载，评分器需要遵循以下规范：

```python
# 1. 使用@register装饰器进行自动注册
@register("my_hot_reload_scorer")
class MyHotReloadScorer:
    name = "my_hot_reload_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 实现细节...
        pass

# 2. 避免模块级全局变量影响重加载
# 错误示例：
# GLOBAL_CONFIG = {"param": "value"}  # 避免使用

# 正确示例：
class MyScorer:
    def __init__(self):
        self.config = {"param": "value"}  # 使用实例变量

# 3. 支持模块重新导入
if __name__ == "__main__":
    # 测试代码，在热重载时不会执行
    pass
```

### 自动发现机制

系统支持自动发现文件中的评分器类：

```python
def load_from_file(self, file_path: str, force_reload: bool = False):
    """从文件自动发现并加载评分器"""
    # 导入模块
    module = self._import_module(file_path)
    
    # 自动发现scorer类
    loaded_scorers = {}
    for name, obj in inspect.getmembers(module):
        if (inspect.isclass(obj) and 
            hasattr(obj, 'score') and 
            obj.__module__ == module_name and
            not name.startswith('_')):
            
            # 自动注册
            scorer_name = getattr(obj, 'name', name.lower())
            self.register(scorer_name, obj)
            loaded_scorers[scorer_name] = obj
    
    return loaded_scorers
```

## 数据处理标准

### BaseCSVScorer基类

对于处理CSV格式数据的评分器，推荐继承`BaseCSVScorer`基类：

```python
from autoscorer.scorers.base_csv import BaseCSVScorer

class MyCSVScorer(BaseCSVScorer):
    def _load_ground_truth(self, workspace: Path):
        gt_path = workspace / "input" / "gt.csv"
        return self._load_and_validate_csv(gt_path, ["id", "label"])
    
    def _validate_data_consistency(self, gt_data, pred_data):
        # 使用基类提供的ID一致性校验
        self._validate_id_consistency(gt_data, pred_data)
        
        # 添加算法特定的校验逻辑
        for row_id, row in gt_data.items():
            if not self._is_valid_label(row["label"]):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Invalid label format for ID {row_id}: {row['label']}"
                )
```

**BaseCSVScorer提供的工具方法:**
- `_load_and_validate_csv(path, required_columns)`: CSV文件加载和基础校验
- `_validate_id_consistency(gt_data, pred_data)`: ID一致性检查
- `_get_iso_timestamp()`: 获取ISO格式时间戳

### 数据验证规范

```python
def _validate_data_format(self, gt_data, pred_data):
    """标准数据验证流程"""
    
    # 1. 基础格式检查
    if not self._is_valid_format(gt_data):
        raise AutoscorerError(
            code="BAD_FORMAT",
            message="Ground truth format invalid"
        )
    
    # 2. 数据一致性检查
    if not self._check_consistency(gt_data, pred_data):
        raise AutoscorerError(
            code="MISMATCH",
            message="Data inconsistency between gt and pred"
        )
    
    # 3. 数据完整性检查
    if not self._check_completeness(gt_data, pred_data):
        raise AutoscorerError(
            code="MISSING_DATA",
            message="Incomplete data detected"
        )
```

### JSON数据处理

对于JSON格式数据（如检测任务），使用以下模式：

```python
def _load_and_validate_json(self, path: Path):
    """JSON数据加载和校验"""
    if not path.exists():
        raise AutoscorerError(code="MISSING_FILE", message=f"File not found: {path}")
    
    try:
        import json
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            raise AutoscorerError(
                code="BAD_FORMAT",
                message="JSON must be an array"
            )
        
        return data
        
    except json.JSONDecodeError as e:
        raise AutoscorerError(code="PARSE_ERROR", message=f"Invalid JSON: {e}")
    except UnicodeDecodeError:
        raise AutoscorerError(code="BAD_FORMAT", message="File encoding error, must be UTF-8")
```

## 热重载开发实践

### 支持热重载的评分器开发

#### 1. 基本开发模式

```python
# custom_scorers/my_hot_scorer.py
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
from autoscorer.schemas.result import Result

@register("hot_reload_demo")
class HotReloadDemo(BaseCSVScorer):
    """支持热重载的演示评分器"""
    
    name = "hot_reload_demo"
    version = "1.0.0"  # 修改版本号来测试热重载
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 评分逻辑
        return Result(
            summary={"score": 0.95},  # 修改这个值来测试热重载
            metrics={"accuracy": 0.95},
            versioning={
                "scorer": self.name,
                "version": self.version,
                "message": "Hot reload working!"  # 添加消息来验证重载
            }
        )
```

#### 2. 开发工作流

```bash
# 终端1: 启动API服务器
autoscorer-api

# 终端2: 加载评分器并启用监控
curl -X POST http://localhost:8000/scorers/load \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_hot_scorer.py", "auto_watch": true}'

# 终端3: 测试评分器
curl -X POST http://localhost:8000/scorers/test \
  -H 'Content-Type: application/json' \
  -d '{"scorer_name": "hot_reload_demo", "workspace": "examples/classification"}'

# 修改my_hot_scorer.py文件，系统会自动重新加载
# 再次测试可以看到新的结果
```

#### 3. 热重载最佳实践

**避免模块级全局状态:**

```python
# ❌ 错误方式 - 模块级全局变量
GLOBAL_CONFIG = {"threshold": 0.5}  # 重载时可能不会更新

class BadScorer:
    def score(self, workspace, params):
        threshold = GLOBAL_CONFIG["threshold"]  # 可能使用旧值
        # ...

# ✅ 正确方式 - 实例级配置
class GoodScorer:
    def __init__(self):
        self.config = {"threshold": 0.5}  # 每次实例化都会更新
    
    def score(self, workspace, params):
        threshold = self.config["threshold"]
        # ...
```

**支持参数化配置:**

```python
@register("configurable_scorer")
class ConfigurableScorer(BaseCSVScorer):
    name = "configurable_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 从params获取配置，支持动态参数
        threshold = params.get("threshold", 0.5)
        mode = params.get("mode", "standard")
        
        # 使用配置进行评分
        if mode == "strict":
            threshold *= 1.2
        
        # 评分逻辑...
        return Result(...)
```

#### 4. 版本管理策略

```python
@register("versioned_scorer")
class VersionedScorer(BaseCSVScorer):
    name = "versioned_scorer"
    version = "1.2.0"  # 语义化版本号
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 版本兼容性处理
        api_version = params.get("api_version", "1.0")
        
        if api_version.startswith("1.0"):
            return self._score_v1_0(workspace, params)
        elif api_version.startswith("1.1"):
            return self._score_v1_1(workspace, params)
        else:
            return self._score_latest(workspace, params)
    
    def _score_v1_0(self, workspace, params):
        """兼容v1.0 API"""
        # 旧版本逻辑
        pass
    
    def _score_latest(self, workspace, params):
        """最新版本逻辑"""
        # 新版本逻辑
        pass
```

### 监控和调试

#### 日志集成

```python
import logging
from autoscorer.utils.logger import get_logger

@register("logged_scorer")
class LoggedScorer(BaseCSVScorer):
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    def score(self, workspace: Path, params: Dict) -> Result:
        self.logger.info(f"Starting evaluation for workspace: {workspace}")
        
        try:
            # 评分逻辑
            result = self._compute_score(workspace, params)
            self.logger.info(f"Evaluation completed successfully: {result.summary}")
            return result
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}", exc_info=True)
            raise
```

#### 性能监控

```python
import time
from functools import wraps

def timing_decorator(func):
    """性能计时装饰器"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            execution_time = time.time() - start_time
            
            # 添加时间信息到结果中
            if hasattr(result, 'timing'):
                result.timing.update({
                    f"{func.__name__}_time": execution_time,
                    "total_time": execution_time
                })
            
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"{func.__name__} failed after {execution_time:.2f}s: {e}")
            raise
    return wrapper

@register("monitored_scorer")
class MonitoredScorer(BaseCSVScorer):
    @timing_decorator
    def score(self, workspace: Path, params: Dict) -> Result:
        # 评分逻辑
        pass
```

### 测试和验证

#### 单元测试支持

```python
# tests/test_hot_reload_scorer.py
import unittest
import tempfile
from pathlib import Path
from autoscorer.scorers.registry import get_scorer, load_scorer_file

class TestHotReloadScorer(unittest.TestCase):
    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        
        # 创建测试数据
        self._create_test_data()
    
    def test_scorer_functionality(self):
        """测试评分器基本功能"""
        # 加载评分器
        load_scorer_file("custom_scorers/my_hot_scorer.py")
        scorer = get_scorer("hot_reload_demo")
        
        # 执行评分
        result = scorer.score(self.workspace, {})
        
        # 验证结果
        self.assertIn("score", result.summary)
        self.assertGreater(result.summary["score"], 0)
    
    def test_hot_reload(self):
        """测试热重载功能"""
        # 首次加载
        load_scorer_file("custom_scorers/my_hot_scorer.py")
        scorer1 = get_scorer("hot_reload_demo")
        result1 = scorer1.score(self.workspace, {})
        
        # 模拟文件修改和重新加载
        # (在实际测试中，可以修改文件内容)
        load_scorer_file("custom_scorers/my_hot_scorer.py", force_reload=True)
        scorer2 = get_scorer("hot_reload_demo")
        result2 = scorer2.score(self.workspace, {})
        
        # 验证重载成功
        self.assertIsNotNone(result2)
    
    def _create_test_data(self):
        """创建测试数据"""
        # 创建gt.csv
        gt_path = self.workspace / "input"
        gt_path.mkdir(parents=True, exist_ok=True)
        with (gt_path / "gt.csv").open("w") as f:
            f.write("id,label\n1,cat\n2,dog\n")
        
        # 创建pred.csv
        pred_path = self.workspace / "output"
        pred_path.mkdir(parents=True, exist_ok=True)
        with (pred_path / "pred.csv").open("w") as f:
            f.write("id,label\n1,cat\n2,dog\n")
```

#### 集成测试

```python
# integration_test.py
import requests
import time

def test_api_hot_reload():
    """测试API层面的热重载功能"""
    base_url = "http://localhost:8000"
    
    # 1. 加载评分器
    response = requests.post(f"{base_url}/scorers/load", json={
        "file_path": "custom_scorers/my_hot_scorer.py",
        "auto_watch": True
    })
    assert response.status_code == 200
    
    # 2. 测试评分器
    response = requests.post(f"{base_url}/scorers/test", json={
        "scorer_name": "hot_reload_demo",
        "workspace": "examples/classification"
    })
    assert response.status_code == 200
    original_result = response.json()
    
    # 3. 手动重新加载
    response = requests.post(f"{base_url}/scorers/reload", json={
        "file_path": "custom_scorers/my_hot_scorer.py"
    })
    assert response.status_code == 200
    
    # 4. 再次测试
    response = requests.post(f"{base_url}/scorers/test", json={
        "scorer_name": "hot_reload_demo", 
        "workspace": "examples/classification"
    })
    assert response.status_code == 200
    reloaded_result = response.json()
    
    print("Hot reload test passed!")
    print(f"Original: {original_result['data']['result']['summary']}")
    print(f"Reloaded: {reloaded_result['data']['result']['summary']}")

if __name__ == "__main__":
    test_api_hot_reload()
```

## 标准化输出规范

### Result对象结构

所有评分器必须返回标准化的`Result`对象：

```python
from autoscorer.schemas.result import Result

result = Result(
    summary={                    # 核心指标摘要
        "score": 0.85,           # 主要评分指标 (必需)
        "rank": "A",             # 等级评定 (可选)
        "pass": True             # 是否通过 (可选)
    },
    metrics={                    # 详细指标
        "f1_macro": 0.85,
        "precision": 0.83,
        "recall": 0.87,
        "per_class_metrics": {...}
    },
    artifacts={                  # 产物文件信息 (可选)
        "confusion_matrix": {
            "path": "/path/to/cm.png",
            "size": 1024,
            "type": "image/png"
        }
    },
    timing={                     # 性能统计 (可选)
        "data_loading": 1.2,
        "computation": 5.8,
        "total": 7.0
    },
    resources={                  # 资源使用 (可选)
        "memory_peak": "512MB",
        "cpu_usage": 2.1
    },
    versioning={                 # 版本信息 (必需)
        "scorer": "my_algorithm",
        "version": "1.0.0",
        "algorithm": "Custom Algorithm",
        "timestamp": "2024-12-01T10:00:00Z"
    }
)
```

### 错误处理标准

```python
from autoscorer.utils.errors import AutoscorerError

# 标准错误码
ERROR_CODES = {
    "BAD_FORMAT": "数据格式错误",
    "MISMATCH": "数据不匹配", 
    "MISSING_FILE": "文件缺失",
    "TYPE_ERROR": "数据类型错误",
    "PARSE_ERROR": "解析错误",
    "SCORE_ERROR": "评分计算错误"
}

# 统一错误处理
try:
    # 评分逻辑
    pass
except AutoscorerError:
    raise  # 重新抛出AutoscorerError
except Exception as e:
    raise AutoscorerError(
        code="SCORE_ERROR",
        message=f"Unexpected error in {self.name}: {str(e)}",
        details={
            "algorithm": self.name,
            "version": self.version,
            "original_error": str(e)
        }
    )
```

## 实际算法实现示例

### 1. 分类F1评分器 (热重载兼容)

```python
# custom_scorers/classification_f1_v2.py
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError

@register("classification_f1_v2")
class ClassificationF1V2(BaseCSVScorer):
    """分类F1评分器 - 支持热重载版本"""
    
    name = "classification_f1_v2"
    version = "2.1.0"  # 修改版本号测试热重载
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """F1分数计算主入口"""
        try:
            # 1. 加载和校验数据
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            
            # 2. 数据一致性校验
            self._validate_data_consistency(gt_data, pred_data)
            
            # 3. 计算F1指标
            metrics = self._compute_f1_metrics(gt_data, pred_data, params)
            
            # 4. 生成等级和通过状态
            f1_score = metrics["f1_macro"]
            rank = self._get_rank(f1_score)
            is_pass = f1_score >= params.get("pass_threshold", 0.6)
            
            # 5. 返回标准化结果
            return Result(
                summary={
                    "score": f1_score,
                    "f1_macro": f1_score,
                    "rank": rank,
                    "pass": is_pass
                },
                metrics=metrics,
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name,
                    "version": self.version,
                    "algorithm": "Macro-F1 Score with Hot Reload",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"F1 calculation failed: {str(e)}",
                details={"algorithm": self.name, "version": self.version}
            )
    
    def _get_rank(self, f1_score: float) -> str:
        """根据F1分数计算等级"""
        if f1_score >= 0.9:
            return "A+"
        elif f1_score >= 0.8:
            return "A"
        elif f1_score >= 0.7:
            return "B"
        elif f1_score >= 0.6:
            return "C"
        else:
            return "D"
    
    def _compute_f1_metrics(self, gt_data, pred_data, params):
        """计算F1指标 - 支持参数化配置"""
        # 获取配置参数
        average_method = params.get("average", "macro")  # macro/micro/weighted
        
        # 提取标签
        gt_labels = {k: v["label"] for k, v in gt_data.items()}
        pred_labels = {k: v["label"] for k, v in pred_data.items()}
        
        # 获取所有唯一标签
        unique_labels = sorted(set(gt_labels.values()))
        
        # 计算每个标签的指标
        per_label_metrics = {}
        total_tp, total_fp, total_fn = 0, 0, 0
        
        for label in unique_labels:
            tp = sum(1 for k in gt_labels 
                    if gt_labels[k] == label and pred_labels[k] == label)
            fp = sum(1 for k in pred_labels 
                    if pred_labels[k] == label and gt_labels[k] != label)
            fn = sum(1 for k in gt_labels 
                    if gt_labels[k] == label and pred_labels[k] != label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            per_label_metrics[f"f1_{label}"] = f1
            per_label_metrics[f"precision_{label}"] = precision
            per_label_metrics[f"recall_{label}"] = recall
            
            total_tp += tp
            total_fp += fp
            total_fn += fn
        
        # 计算不同平均方法的F1
        if average_method == "macro":
            macro_f1 = sum(per_label_metrics[f"f1_{label}"] for label in unique_labels) / len(unique_labels)
        elif average_method == "micro":
            micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
            micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
            macro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0.0
        
        return {
            "f1_macro": macro_f1,
            "num_labels": len(unique_labels),
            "total_samples": len(gt_labels),
            "average_method": average_method,
            **per_label_metrics
        }
```

### 2. 回归评分器 (支持多指标)

```python
# custom_scorers/regression_multi.py
import math
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("regression_multi")
class RegressionMultiMetric(BaseCSVScorer):
    """多指标回归评分器"""
    
    name = "regression_multi"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        try:
            # 数据加载
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            self._validate_data_consistency(gt_data, pred_data)
            
            # 转换为数值
            gt_values = self._extract_numeric_values(gt_data, "GT")
            pred_values = self._extract_numeric_values(pred_data, "Prediction")
            
            # 计算多种指标
            metrics = self._compute_regression_metrics(gt_values, pred_values, params)
            
            # 主要指标选择
            primary_metric = params.get("primary_metric", "rmse")
            primary_score = metrics[primary_metric]
            
            return Result(
                summary={
                    "score": primary_score,
                    primary_metric: primary_score,
                    "rank": self._get_regression_rank(primary_score, primary_metric)
                },
                metrics=metrics,
                versioning={
                    "scorer": self.name,
                    "version": self.version,
                    "algorithm": f"Multi-Metric Regression ({primary_metric.upper()})",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"Regression evaluation failed: {str(e)}"
            )
    
    def _compute_regression_metrics(self, gt_values, pred_values, params):
        """计算多种回归指标"""
        n = len(gt_values)
        
        # 基础误差计算
        errors = [gt - pred for gt, pred in zip(gt_values, pred_values)]
        abs_errors = [abs(e) for e in errors]
        squared_errors = [e ** 2 for e in errors]
        
        # MAE (平均绝对误差)
        mae = sum(abs_errors) / n
        
        # MSE (均方误差)
        mse = sum(squared_errors) / n
        
        # RMSE (均方根误差)
        rmse = math.sqrt(mse)
        
        # R² (决定系数)
        gt_mean = sum(gt_values) / n
        ss_tot = sum((gt - gt_mean) ** 2 for gt in gt_values)
        ss_res = sum(squared_errors)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # MAPE (平均绝对百分比误差)
        mape = sum(abs(e / gt) for e, gt in zip(errors, gt_values) if gt != 0) / n * 100
        
        return {
            "mae": mae,
            "mse": mse,
            "rmse": rmse,
            "r_squared": r_squared,
            "mape": mape,
            "gt_mean": sum(gt_values) / n,
            "pred_mean": sum(pred_values) / n,
            "n_samples": n
        }
```

## 部署和集成

### 模块化部署

每个评分器模块可以独立部署和热更新：

```python
# 部署新的评分器模块
# custom_scorers/production_scorer.py
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("production_scorer_v1")
class ProductionScorerV1(BaseCSVScorer):
    name = "production_scorer_v1"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 生产环境评分逻辑
        pass
```

### 第三方算法集成

支持第三方开发者创建独立的算法包：

```python
# third_party_scorers.py
from autoscorer.scorers.registry import register

@register("custom_nlp_scorer")
class CustomNLPScorer:
    name = "custom_nlp_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 第三方NLP评分实现
        pass

# 动态加载第三方评分器
from autoscorer.scorers.registry import load_scorer_file

# 加载并启用监控
loaded_scorers = load_scorer_file("third_party_scorers.py")
start_watching_file("third_party_scorers.py")
```

### 配置和管理

```python
# 获取所有已注册的评分器
from autoscorer.scorers.registry import list_scorers, get_scorer

# 列出所有评分器
scorers = list_scorers()
for name, description in scorers.items():
    print(f"评分器: {name} - {description}")

# 动态获取和使用评分器
scorer = get_scorer("classification_f1_v2")
if scorer:
    result = scorer.score(workspace, params)
else:
    print("评分器未找到")
```

### 生产环境最佳实践

#### 1. 版本管理

```python
@register("stable_scorer")
class StableScorer(BaseCSVScorer):
    name = "stable_scorer"
    version = "2.1.0"
    
    # 支持API版本兼容性
    SUPPORTED_API_VERSIONS = ["2.0", "2.1"]
    
    def score(self, workspace: Path, params: Dict) -> Result:
        api_version = params.get("api_version", "2.1")
        
        if api_version not in self.SUPPORTED_API_VERSIONS:
            raise AutoscorerError(
                code="UNSUPPORTED_VERSION",
                message=f"API version {api_version} not supported"
            )
        
        # 根据API版本调用对应的实现
        if api_version.startswith("2.0"):
            return self._score_v2_0(workspace, params)
        else:
            return self._score_v2_1(workspace, params)
```

#### 2. 性能优化

```python
@register("optimized_scorer")
class OptimizedScorer(BaseCSVScorer):
    def __init__(self):
        # 缓存机制
        self._cache = {}
        self._cache_size_limit = 1000
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 缓存键
        cache_key = self._generate_cache_key(workspace, params)
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 计算结果
        result = self._compute_score(workspace, params)
        
        # 缓存结果
        if len(self._cache) < self._cache_size_limit:
            self._cache[cache_key] = result
        
        return result
```

#### 3. 监控和日志

```python
@register("monitored_scorer")
class MonitoredScorer(BaseCSVScorer):
    def __init__(self):
        self.metrics_collector = MetricsCollector()
    
    def score(self, workspace: Path, params: Dict) -> Result:
        start_time = time.time()
        
        try:
            result = self._compute_score(workspace, params)
            
            # 记录成功指标
            self.metrics_collector.record_success(
                scorer=self.name,
                execution_time=time.time() - start_time,
                score=result.summary.get("score")
            )
            
            return result
            
        except Exception as e:
            # 记录失败指标
            self.metrics_collector.record_failure(
                scorer=self.name,
                error_type=type(e).__name__,
                execution_time=time.time() - start_time
            )
            raise
```
