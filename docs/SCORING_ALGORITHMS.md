# AutoScorer 评分算法实现标准

## 概述

本文档基于AutoScorer v2.0实际代码实现，详细说明各类评分算法的功能实现、注册机制、数据格式要求和使用方法。

## 目录

1. [评分器注册系统](#评分器注册系统)
2. [已实现评分算法](#已实现评分算法)
   - [分类评分器](#分类评分器)
   - [回归评分器](#回归评分器)
   - [检测评分器](#检测评分器)
3. [基础架构](#基础架构)
4. [数据格式标准](#数据格式标准)
5. [自定义评分器开发](#自定义评分器开发)

---

## 评分器注册系统

### 架构设计

AutoScorer采用基于装饰器的动态注册系统，支持热重载和线程安全的评分器管理。

**核心组件：**

```python
# 注册器实现 (src/autoscorer/scorers/registry.py)
class ScorerRegistry:
    def __init__(self):
        self._scorers = {}
        self._lock = threading.Lock()
    
    def register(self, name: str, scorer_class: type):
        """线程安全的评分器注册"""
        with self._lock:
            self._scorers[name] = scorer_class
    
    def get(self, name: str):
        """获取评分器类"""
        return self._scorers.get(name)
```

**注册装饰器：**

```python
def register(name: str):
    """评分器注册装饰器"""
    def decorator(cls):
        registry.register(name, cls)
        return cls
    return decorator
```

### 已注册评分器列表

| 评分器名称 | 注册ID | 任务类型 | 实现类 |
|-----------|--------|----------|--------|
| F1-Score | `classification_f1` | 分类 | `ClassificationF1` |
| Accuracy | `classification_accuracy` | 分类 | `ClassificationAccuracy` |
| RMSE | `regression_rmse` | 回归 | `RegressionRMSE` |
| mAP | `detection_map` | 检测 | `DetectionMAP` |

### 动态加载机制

- **热重载**: 支持运行时加载新的评分器文件
- **文件监控**: 自动检测`custom_scorers/`目录变化
- **线程安全**: 并发环境下的安全注册和访问

---

## 已实现评分算法

### 分类评分器

#### 1. F1-Score 评分器

**注册ID**: `classification_f1`  
**实现类**: `ClassificationF1`  
**位置**: `src/autoscorer/scorers/classification.py`

**功能特性：**
- 支持多类别分类任务
- 计算宏平均F1分数 (Macro-F1)
- 基于混淆矩阵的精确率和召回率计算
- 标准化Result格式输出

**算法实现：**

```python
@register("classification_f1")
class ClassificationF1(BaseCSVScorer):
    name = "classification_f1"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 1. 数据加载和验证
        gt_data = self._load_and_validate_csv(ws / "input" / "gt.csv", ["id", "label"])
        pred_data = self._load_and_validate_csv(ws / "output" / "pred.csv", ["id", "label"])
        
        # 2. ID一致性检查
        self._validate_id_consistency(gt_data, pred_data)
        
        # 3. F1计算
        confusion_matrix = self._build_confusion_matrix(gt_data, pred_data)
        f1_scores = self._calculate_f1_per_class(confusion_matrix)
        macro_f1 = sum(f1_scores.values()) / len(f1_scores)
        
        # 4. 返回标准结果
        return Result(summary={"score": macro_f1}, ...)
```

**数据格式要求：**

输入文件(`gt.csv`):
```csv
id,label
1,cat
2,dog
3,cat
```

输出文件(`pred.csv`):
```csv
id,label
1,cat
2,dog
3,dog
```

**输出结果示例：**

```json
{
  "summary": {
    "score": 0.667,
    "f1_macro": 0.667
  },
  "metrics": {
    "f1_macro": 0.667,
    "f1_cat": 0.500,
    "f1_dog": 0.833,
    "num_labels": 2,
    "total_samples": 3.0
  },
  "versioning": {
    "scorer": "classification_f1",
    "version": "2.0.0",
    "algorithm": "Macro-F1 Score"
  }
}
```

#### 2. Accuracy 评分器

**注册ID**: `classification_accuracy`  
**实现类**: `ClassificationAccuracy`  
**位置**: `src/autoscorer/scorers/classification.py`

**功能特性：**
- 计算总体分类准确率
- 可选的按类别准确率统计
- 简单高效的正确率计算

**算法实现：**

```python
@register("classification_accuracy")
class ClassificationAccuracy(BaseCSVScorer):
    name = "classification_accuracy"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 数据处理同F1评分器
        correct = sum(1 for item_id in gt_data.keys() 
                     if gt_data[item_id]["label"] == pred_data[item_id]["label"])
        accuracy = correct / len(gt_data)
        
        return Result(summary={"score": accuracy, "accuracy": accuracy}, ...)
```

**输出结果示例：**

```json
{
  "summary": {
    "score": 0.667,
    "accuracy": 0.667
  },
  "metrics": {
    "accuracy": 0.667,
    "correct": 2.0,
    "total": 3.0,
    "num_classes": 2
  }
}
```

### 回归评分器

#### RMSE 评分器

**注册ID**: `regression_rmse`  
**实现类**: `RegressionRMSE`  
**位置**: `src/autoscorer/scorers/regression.py`

**功能特性：**
- 计算均方根误差 (RMSE)
- 同时计算MSE、MAE、R²等补充指标
- 数值验证和异常处理
- 统计描述信息

**算法实现：**

```python
@register("regression_rmse")
class RegressionRMSE(BaseCSVScorer):
    name = "regression_rmse"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 数据加载
        gt_data = self._load_and_validate_csv(ws / "input" / "gt.csv", ["id", "value"])
        pred_data = self._load_and_validate_csv(ws / "output" / "pred.csv", ["id", "value"])
        
        # 数值验证和计算
        gt_values, pred_values = self._extract_and_validate_values(gt_data, pred_data)
        
        # 多指标计算
        mse = sum((gt - pred) ** 2 for gt, pred in zip(gt_values, pred_values)) / len(gt_values)
        rmse = math.sqrt(mse)
        mae = sum(abs(gt - pred) for gt, pred in zip(gt_values, pred_values)) / len(gt_values)
        r_squared = self._calculate_r_squared(gt_values, pred_values)
        
        return Result(summary={"score": rmse, "rmse": rmse}, ...)
```

**数据格式要求：**

输入文件(`gt.csv`):
```csv
id,value
1,2.5
2,3.8
3,1.2
```

输出文件(`pred.csv`):
```csv
id,value
1,2.3
2,4.1
3,1.0
```

**输出结果示例：**

```json
{
  "summary": {
    "score": 0.289,
    "rmse": 0.289
  },
  "metrics": {
    "rmse": 0.289,
    "mse": 0.083,
    "mae": 0.233,
    "r_squared": 0.876,
    "gt_mean": 2.5,
    "pred_mean": 2.467,
    "n_samples": 3.0
  }
}
```

### 检测评分器

#### mAP 评分器

**注册ID**: `detection_map`  
**实现类**: `DetectionMAP`  
**位置**: `src/autoscorer/scorers/detection.py`

**功能特性：**
- 目标检测平均精度均值计算
- IoU阈值可配置
- 简化版mAP实现(生产环境建议使用专业库)
- 支持多类别目标检测

**算法实现：**

```python
@register("detection_map")
class DetectionMAP(BaseCSVScorer):
    name = "detection_map"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # JSON格式数据加载
        gt_data = self._load_ground_truth(ws)
        pred_data = self._load_predictions(ws)
        
        # 数据格式验证
        self._validate_detection_data(gt_data, pred_data)
        
        # mAP计算
        metrics = self._compute_map_metrics(gt_data, pred_data, params)
        
        return Result(summary={"score": metrics["mAP"]}, ...)
```

**数据格式要求：**

输入文件(`gt.json`):
```json
[
  {
    "image_id": "img_001",
    "bbox": [10, 10, 50, 60],
    "category_id": 1
  },
  {
    "image_id": "img_001", 
    "bbox": [80, 20, 40, 50],
    "category_id": 2
  }
]
```

输出文件(`pred.json`):
```json
[
  {
    "image_id": "img_001",
    "bbox": [12, 8, 48, 65],
    "category_id": 1,
    "score": 0.85
  },
  {
    "image_id": "img_001",
    "bbox": [75, 25, 35, 45], 
    "category_id": 2,
    "score": 0.72
  }
]
```

**输出结果示例：**

```json
{
  "summary": {
    "score": 0.675,
    "mAP": 0.675,
    "rank": "B",
    "pass": true
  },
  "metrics": {
    "mAP": 0.675,
    "num_categories": 2,
    "total_gt_boxes": 100.0,
    "total_pred_boxes": 95.0,
    "iou_threshold": 0.5,
    "score_threshold": 0.0,
    "AP_class_1": 0.72,
    "AP_class_2": 0.63
  }
}
```

---

## 基础架构

### BaseCSVScorer 基类

**位置**: `src/autoscorer/scorers/base_csv.py`

**提供功能：**
- CSV文件标准加载和验证
- UTF-8编码处理
- ID一致性检查
- 时间戳生成
- 错误处理包装

**核心方法：**

```python
class BaseCSVScorer:
    def _load_and_validate_csv(self, path: Path, required_columns: list) -> Dict[str, str]:
        """加载CSV并验证格式"""
        
    def _validate_id_consistency(self, gt_data: Dict, pred_data: Dict):
        """验证GT和预测的ID一致性"""
        
    def _get_iso_timestamp(self) -> str:
        """获取ISO格式时间戳"""
```

### Result 标准化输出

**位置**: `src/autoscorer/schemas/result.py`

**字段规范：**
- `summary`: 主要评分结果和等级
- `metrics`: 详细计算指标
- `artifacts`: 附加文件信息
- `timing`: 执行时间统计
- `resources`: 资源使用情况
- `versioning`: 版本和算法信息

---

## 数据格式标准

### CSV格式要求

**分类任务:**
- 必需列: `id`, `label`
- ID格式: 字符串或数字,唯一标识
- 标签格式: 字符串类别名
- 编码: UTF-8

**回归任务:**
- 必需列: `id`, `value`
- ID格式: 字符串或数字,唯一标识
- 数值格式: 数字(整数或浮点数)
- 编码: UTF-8

### JSON格式要求

**检测任务:**
- 文件格式: JSON数组
- 边界框格式: `[x, y, width, height]`
- 类别ID: 整数
- 置信度: 0-1之间的浮点数(仅预测)

### 文件结构标准

```
workspace/
├── input/
│   ├── gt.csv      # 分类/回归标准答案
│   └── gt.json     # 检测标准答案
└── output/
    ├── pred.csv    # 分类/回归预测结果
    └── pred.json   # 检测预测结果
```

---

## 自定义评分器开发

### 开发指南

1. **继承基类**: 从`BaseCSVScorer`继承(CSV任务)或实现自定义基类
2. **注册装饰器**: 使用`@register("custom_name")`装饰器
3. **实现score方法**: 核心评分逻辑
4. **返回Result**: 使用标准化的Result格式

### 评分器模板

```python
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
from autoscorer.schemas.result import Result

@register("custom_scorer")
class CustomScorer(BaseCSVScorer):
    name = "custom_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """自定义评分逻辑"""
        try:
            # 1. 数据加载
            gt_data = self._load_and_validate_csv(
                workspace / "input" / "gt.csv",
                ["id", "custom_field"]
            )
            pred_data = self._load_and_validate_csv(
                workspace / "output" / "pred.csv", 
                ["id", "custom_field"]
            )
            
            # 2. 数据验证
            self._validate_id_consistency(gt_data, pred_data)
            
            # 3. 自定义计算逻辑
            score_value = self._custom_calculation(gt_data, pred_data)
            
            # 4. 返回标准结果
            return Result(
                summary={"score": score_value},
                metrics={"custom_metric": score_value},
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name,
                    "version": self.version,
                    "algorithm": "Custom Algorithm",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"Custom scoring failed: {str(e)}"
            )
    
    def _custom_calculation(self, gt_data: Dict, pred_data: Dict) -> float:
        """自定义计算逻辑实现"""
        # 实现您的评分算法
        pass
```

### 部署自定义评分器

1. **放置文件**: 将评分器放入`custom_scorers/`目录
2. **自动加载**: 系统会自动检测并加载新评分器
3. **使用注册ID**: 在meta.json中指定注册的评分器名称

**示例 meta.json:**

```json
{
    "scorer": "custom_scorer",
    "params": {
        "threshold": 0.5,
        "custom_param": "value"
    }
}
```

### 测试自定义评分器

```python
# 测试示例
from autoscorer.scorers.registry import registry

# 获取评分器
scorer_class = registry.get("custom_scorer")
scorer = scorer_class()

# 执行评分
result = scorer.score(workspace_path, params)
print(result.summary)
```



