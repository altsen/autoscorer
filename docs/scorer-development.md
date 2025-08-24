# 评分器开发指南

本文档详细说明如何开发自定义评分器，包括设计原则、接口规范、实现示例和最佳实践。

## 评分器概述

评分器是 AutoScorer 系统的核心组件，负责根据预测结果和标准答案计算评分指标。系统支持插件化的评分器架构，允许开发者创建满足特定需求的自定义算法。

### 设计原则

- **标准化接口**: 统一的评分器基类和调用规范
- **插件化架构**: 支持动态加载和注册
- **热重载支持**: 开发时无需重启服务
- **版本管理**: 完整的版本控制和兼容性管理
- **可扩展性**: 简单的接口便于扩展新算法

### 支持的任务类型

| 任务类型 | 数据格式 | 常见指标 | 示例场景 |
|----------|----------|----------|----------|
| 分类 (classification) | CSV | F1, Accuracy, Precision | 图像分类、文本分类 |
| 回归 (regression) | CSV | RMSE, MAE, R² | 价格预测、销量预测 |
| 检测 (detection) | JSON | mAP, IoU | 目标检测、人脸检测 |
| 分割 (segmentation) | JSON/Images | IoU, Dice | 语义分割、实例分割 |
| 文本生成 (generation) | CSV/JSON | BLEU, ROUGE | 机器翻译、文本摘要 |

## 基础接口

### 核心接口定义

所有评分器都必须实现 `BaseScorer` 基类：

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
from autoscorer.schemas.result import Result

class BaseScorer(ABC):
    """评分器基类 - 定义标准接口"""
    
    # 必需属性
    name: str = NotImplemented          # 评分器唯一标识符
    version: str = NotImplemented       # 语义化版本号
    description: str = ""               # 评分器描述
    
    # 可选属性
    author: str = ""                    # 作者信息
    supported_task_types: List[str] = []  # 支持的任务类型
    supported_formats: List[str] = []   # 支持的数据格式
    
    @abstractmethod
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        """
        评分主入口方法
        
        Args:
            workspace: 工作区路径，包含输入输出数据
            params: 评分参数，来自 meta.json 的 scorer_params
            
        Returns:
            Result: 标准化的评分结果对象
            
        Raises:
            AutoscorerError: 评分过程中的各种错误
        """
        pass
    
    def validate_workspace(self, workspace: Path) -> bool:
        """
        验证工作区是否符合要求 (可选重写)
        
        Args:
            workspace: 工作区路径
            
        Returns:
            bool: 工作区是否有效
        """
        return True
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        获取参数结构定义 (可选重写)
        
        Returns:
            Dict: 参数的 JSON Schema 定义
        """
        return {}
```

### 注册装饰器

使用 `@register` 装饰器将评分器注册到系统：

```python
from autoscorer.scorers.registry import register

@register("my_custom_scorer")  # 指定评分器名称
class MyCustomScorer(BaseScorer):
    name = "my_custom_scorer"
    version = "1.0.0"
    description = "自定义评分器示例"
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        # 实现评分逻辑
        pass
```

## 数据处理

### CSV 数据处理基类

对于处理 CSV 格式数据的评分器，推荐继承 `BaseCSVScorer`：

```python
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("csv_based_scorer")
class CSVBasedScorer(BaseCSVScorer):
    name = "csv_based_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        # 1. 加载数据 (基类提供工具方法)
        gt_data = self._load_ground_truth(workspace)
        pred_data = self._load_predictions(workspace)
        
        # 2. 验证数据一致性
        self._validate_data_consistency(gt_data, pred_data)
        
        # 3. 计算指标
        metrics = self._compute_metrics(gt_data, pred_data, params)
        
        # 4. 返回结果
        return self._create_result(metrics)
    
    def _load_ground_truth(self, workspace: Path) -> Dict[str, Dict[str, Any]]:
        """加载标准答案数据"""
        gt_path = workspace / "input" / "gt.csv"
        return self._load_and_validate_csv(gt_path, ["id", "label"])
    
    def _load_predictions(self, workspace: Path) -> Dict[str, Dict[str, Any]]:
        """加载预测结果数据"""
        pred_path = workspace / "output" / "pred.csv"
        return self._load_and_validate_csv(pred_path, ["id", "label"])
    
    def _compute_metrics(self, gt_data, pred_data, params):
        """计算评分指标 - 子类实现"""
        # 具体计算逻辑
        return {"main_metric": 0.85}
```

### JSON 数据处理

对于 JSON 格式数据（如目标检测），使用以下模式：

```python
import json
from typing import Union, List, Dict

@register("json_based_scorer")
class JSONBasedScorer(BaseScorer):
    name = "json_based_scorer"
    version = "1.0.0"
    
    def _load_json_data(self, file_path: Path) -> Union[Dict, List]:
        """通用 JSON 数据加载方法"""
        if not file_path.exists():
            raise AutoscorerError(
                code="MISSING_FILE",
                message=f"Required file not found: {file_path}"
            )
        
        try:
            with file_path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise AutoscorerError(
                code="PARSE_ERROR",
                message=f"Invalid JSON format: {e}"
            )
        except UnicodeDecodeError:
            raise AutoscorerError(
                code="ENCODING_ERROR",
                message="File must be UTF-8 encoded"
            )
    
    def _validate_json_format(self, data: Any, expected_format: str) -> bool:
        """验证 JSON 数据格式"""
        if expected_format == "coco_detection":
            return self._validate_coco_format(data)
        elif expected_format == "yolo_detection":
            return self._validate_yolo_format(data)
        else:
            return True
    
    def _validate_coco_format(self, data: Dict) -> bool:
        """验证 COCO 格式"""
        required_keys = ["images", "annotations", "categories"]
        return all(key in data for key in required_keys)
```

## 评分器实现示例

### 示例 1: 自定义分类评分器

```python
import pandas as pd
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
from autoscorer.schemas.result import Result, Summary

@register("enhanced_classification")
class EnhancedClassificationScorer(BaseCSVScorer):
    """
    增强型分类评分器
    支持多种平均策略、类别权重和阈值设置
    """
    
    name = "enhanced_classification"
    version = "1.2.0"
    description = "Enhanced classification scorer with weighted metrics"
    author = "AutoScorer Team"
    supported_task_types = ["classification"]
    supported_formats = ["csv"]
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        """执行增强型分类评分"""
        start_time = time.time()
        
        try:
            # 1. 数据加载和验证
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            self._validate_data_consistency(gt_data, pred_data)
            
            # 2. 参数处理
            validated_params = self._validate_parameters(params)
            
            # 3. 数据预处理
            gt_labels, pred_labels = self._prepare_labels(gt_data, pred_data, validated_params)
            
            # 4. 计算指标
            metrics = self._compute_enhanced_metrics(gt_labels, pred_labels, validated_params)
            
            # 5. 生成结果
            return self._create_enhanced_result(metrics, time.time() - start_time)
            
        except Exception as e:
            if isinstance(e, AutoscorerError):
                raise
            else:
                raise AutoscorerError(
                    code="SCORING_ERROR",
                    message=f"Scoring failed: {str(e)}",
                    details={"scorer": self.name, "version": self.version}
                )
    
    def _validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证和标准化参数"""
        default_params = {
            "average": "macro",
            "labels": None,
            "sample_weight": None,
            "class_weights": None,
            "threshold": 0.5,
            "pos_label": 1,
            "zero_division": 0
        }
        
        # 合并参数
        validated = {**default_params, **params}
        
        # 参数验证
        if validated["average"] not in ["macro", "micro", "weighted", "binary"]:
            raise AutoscorerError(
                code="INVALID_PARAMETER",
                message=f"Invalid average method: {validated['average']}"
            )
        
        if validated["threshold"] < 0 or validated["threshold"] > 1:
            raise AutoscorerError(
                code="INVALID_PARAMETER", 
                message="Threshold must be between 0 and 1"
            )
        
        return validated
    
    def _prepare_labels(self, gt_data, pred_data, params):
        """准备标签数据"""
        # 按 ID 排序确保对应关系
        gt_sorted = sorted(gt_data.items(), key=lambda x: x[0])
        pred_sorted = sorted(pred_data.items(), key=lambda x: x[0])
        
        gt_labels = [item[1]["label"] for item in gt_sorted]
        pred_labels = [item[1]["label"] for item in pred_sorted]
        
        # 处理概率预测 (如果有 probability 列)
        if "probability" in pred_sorted[0][1]:
            probabilities = [item[1]["probability"] for item in pred_sorted]
            threshold = params["threshold"]
            
            # 将概率转换为标签
            pred_labels = [1 if prob >= threshold else 0 for prob in probabilities]
        
        return gt_labels, pred_labels
    
    def _compute_enhanced_metrics(self, gt_labels, pred_labels, params):
        """计算增强指标"""
        metrics = {}
        
        # 基础指标
        metrics["accuracy"] = accuracy_score(gt_labels, pred_labels)
        
        # F1 指标 (不同平均方法)
        average = params["average"]
        sample_weight = params["sample_weight"]
        labels = params["labels"]
        zero_division = params["zero_division"]
        
        metrics["f1_score"] = f1_score(
            gt_labels, pred_labels, 
            average=average, 
            labels=labels,
            sample_weight=sample_weight,
            zero_division=zero_division
        )
        
        metrics["precision"] = precision_score(
            gt_labels, pred_labels,
            average=average,
            labels=labels, 
            sample_weight=sample_weight,
            zero_division=zero_division
        )
        
        metrics["recall"] = recall_score(
            gt_labels, pred_labels,
            average=average,
            labels=labels,
            sample_weight=sample_weight, 
            zero_division=zero_division
        )
        
        # 按类别指标
        if average in ["macro", "weighted"]:
            unique_labels = sorted(set(gt_labels))
            for label in unique_labels:
                label_f1 = f1_score(gt_labels, pred_labels, labels=[label], average="binary", zero_division=zero_division)
                metrics[f"f1_class_{label}"] = label_f1
        
        # 混淆矩阵
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(gt_labels, pred_labels, labels=labels)
        metrics["confusion_matrix"] = cm.tolist()
        
        # 自定义加权指标
        if params["class_weights"]:
            weighted_f1 = self._calculate_weighted_f1(gt_labels, pred_labels, params["class_weights"])
            metrics["weighted_f1_custom"] = weighted_f1
        
        # 数据统计
        metrics["num_samples"] = len(gt_labels)
        metrics["num_classes"] = len(set(gt_labels))
        
        return metrics
    
    def _calculate_weighted_f1(self, gt_labels, pred_labels, class_weights):
        """计算自定义权重的 F1 分数"""
        unique_labels = sorted(set(gt_labels))
        weighted_sum = 0
        total_weight = 0
        
        for label in unique_labels:
            if label in class_weights:
                label_f1 = f1_score(gt_labels, pred_labels, labels=[label], average="binary", zero_division=0)
                weight = class_weights[label]
                weighted_sum += label_f1 * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0
    
    def _create_enhanced_result(self, metrics, execution_time):
        """创建增强结果对象"""
        # 主要得分
        main_score = metrics["f1_score"]
        
        # 等级评定
        rank = self._calculate_rank(main_score)
        
        # 通过判定
        pass_threshold = 0.6  # 可以从参数传入
        is_pass = main_score >= pass_threshold
        
        return Result(
            summary=Summary(
                score=main_score,
                rank=rank,
                pass=is_pass,
                message=f"Enhanced classification evaluation completed"
            ),
            metrics=metrics,
            artifacts={},
            timing={"total_time": execution_time},
            versioning={
                "scorer": self.name,
                "version": self.version,
                "algorithm": "Enhanced F1 with Custom Weights",
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def _calculate_rank(self, score: float) -> str:
        """计算等级"""
        if score >= 0.95:
            return "S"
        elif score >= 0.9:
            return "A+"
        elif score >= 0.85:
            return "A"
        elif score >= 0.8:
            return "B+"
        elif score >= 0.75:
            return "B"
        elif score >= 0.7:
            return "C+"
        elif score >= 0.65:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """获取参数结构定义"""
        return {
            "type": "object",
            "properties": {
                "average": {
                    "type": "string",
                    "enum": ["macro", "micro", "weighted", "binary"],
                    "default": "macro",
                    "description": "Averaging strategy for multi-class metrics"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": ["string", "number"]},
                    "default": None,
                    "description": "List of labels to include in evaluation"
                },
                "class_weights": {
                    "type": "object",
                    "default": None,
                    "description": "Custom weights for each class"
                },
                "threshold": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.5,
                    "description": "Decision threshold for binary classification"
                }
            }
        }
```

### 示例 2: 回归评分器

```python
import math
from scipy import stats
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("advanced_regression")
class AdvancedRegressionScorer(BaseCSVScorer):
    """
    高级回归评分器
    支持多种回归指标和稳健性统计
    """
    
    name = "advanced_regression"
    version = "1.1.0"
    description = "Advanced regression scorer with robust statistics"
    supported_task_types = ["regression"]
    supported_formats = ["csv"]
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        """执行高级回归评分"""
        try:
            # 数据加载
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            self._validate_data_consistency(gt_data, pred_data)
            
            # 提取数值
            gt_values = self._extract_numeric_values(gt_data)
            pred_values = self._extract_numeric_values(pred_data)
            
            # 计算指标
            metrics = self._compute_regression_metrics(gt_values, pred_values, params)
            
            return self._create_regression_result(metrics)
            
        except Exception as e:
            raise AutoscorerError(
                code="REGRESSION_SCORING_ERROR",
                message=f"Regression scoring failed: {str(e)}"
            )
    
    def _extract_numeric_values(self, data: Dict) -> List[float]:
        """提取数值，支持多种格式"""
        values = []
        for item_id, item_data in data.items():
            value = item_data.get("value") or item_data.get("target") or item_data.get("y")
            
            if value is None:
                raise AutoscorerError(
                    code="MISSING_VALUE",
                    message=f"No numeric value found for item {item_id}"
                )
            
            try:
                values.append(float(value))
            except (ValueError, TypeError):
                raise AutoscorerError(
                    code="INVALID_VALUE",
                    message=f"Invalid numeric value for item {item_id}: {value}"
                )
        
        return values
    
    def _compute_regression_metrics(self, gt_values, pred_values, params):
        """计算回归指标"""
        n = len(gt_values)
        
        # 基础统计
        errors = [gt - pred for gt, pred in zip(gt_values, pred_values)]
        abs_errors = [abs(e) for e in errors]
        squared_errors = [e ** 2 for e in errors]
        
        # 基础指标
        mae = sum(abs_errors) / n  # 平均绝对误差
        mse = sum(squared_errors) / n  # 均方误差
        rmse = math.sqrt(mse)  # 均方根误差
        
        # R² 决定系数
        gt_mean = sum(gt_values) / n
        ss_tot = sum((gt - gt_mean) ** 2 for gt in gt_values)
        ss_res = sum(squared_errors)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # 平均绝对百分比误差 (MAPE)
        mape = sum(abs(e / gt) for e, gt in zip(errors, gt_values) if gt != 0) / n * 100
        
        # 稳健性指标
        median_ae = sorted(abs_errors)[n // 2]  # 中位数绝对误差
        
        # 皮尔逊相关系数
        correlation, p_value = stats.pearsonr(gt_values, pred_values)
        
        # 分位数指标
        q75_error = sorted(abs_errors)[int(n * 0.75)]
        q95_error = sorted(abs_errors)[int(n * 0.95)]
        
        # 最大误差
        max_error = max(abs_errors)
        
        # 标准化指标
        explained_variance = 1 - (sum(squared_errors) / sum((gt - gt_mean) ** 2 for gt in gt_values))
        
        return {
            # 基础指标
            "mae": mae,
            "mse": mse, 
            "rmse": rmse,
            "r_squared": r_squared,
            "mape": mape,
            
            # 稳健性指标
            "median_absolute_error": median_ae,
            "max_error": max_error,
            "q75_error": q75_error,
            "q95_error": q95_error,
            
            # 相关性指标
            "correlation": correlation,
            "correlation_p_value": p_value,
            "explained_variance": explained_variance,
            
            # 数据统计
            "n_samples": n,
            "gt_mean": sum(gt_values) / n,
            "pred_mean": sum(pred_values) / n,
            "gt_std": math.sqrt(sum((x - gt_mean) ** 2 for x in gt_values) / n),
            "pred_std": math.sqrt(sum((x - sum(pred_values) / n) ** 2 for x in pred_values) / n)
        }
    
    def _create_regression_result(self, metrics):
        """创建回归结果"""
        # 主要指标选择 (可通过参数配置)
        primary_metric = "rmse"
        main_score = 1 / (1 + metrics[primary_metric])  # 转换为越大越好的分数
        
        return Result(
            summary=Summary(
                score=main_score,
                rank=self._calculate_regression_rank(metrics[primary_metric]),
                pass=metrics["r_squared"] >= 0.7,  # 基于 R² 判断
                message="Advanced regression evaluation completed"
            ),
            metrics=metrics,
            versioning={
                "scorer": self.name,
                "version": self.version,
                "primary_metric": primary_metric
            }
        )
    
    def _calculate_regression_rank(self, rmse: float) -> str:
        """基于 RMSE 计算等级"""
        if rmse <= 0.1:
            return "S"
        elif rmse <= 0.2:
            return "A"
        elif rmse <= 0.5:
            return "B"
        elif rmse <= 1.0:
            return "C"
        else:
            return "D"
```

### 示例 3: 目标检测评分器

```python
import numpy as np
from typing import List, Dict, Tuple
from autoscorer.scorers.registry import register
from autoscorer.scorers.base import BaseScorer

@register("object_detection_map")
class ObjectDetectionMAPScorer(BaseScorer):
    """
    目标检测 mAP 评分器
    支持 COCO 格式的目标检测评估
    """
    
    name = "object_detection_map"
    version = "1.0.0"
    description = "Object detection mAP scorer with COCO format support"
    supported_task_types = ["detection"]
    supported_formats = ["json"]
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        """执行目标检测评分"""
        try:
            # 加载 COCO 格式数据
            gt_data = self._load_coco_ground_truth(workspace)
            pred_data = self._load_coco_predictions(workspace)
            
            # 计算 mAP
            map_results = self._compute_map(gt_data, pred_data, params)
            
            return self._create_detection_result(map_results)
            
        except Exception as e:
            raise AutoscorerError(
                code="DETECTION_SCORING_ERROR",
                message=f"Detection scoring failed: {str(e)}"
            )
    
    def _load_coco_ground_truth(self, workspace: Path) -> Dict:
        """加载 COCO 格式的标准答案"""
        gt_path = workspace / "input" / "gt.json"
        data = self._load_json_data(gt_path)
        
        # 验证 COCO 格式
        if not self._validate_coco_format(data):
            raise AutoscorerError(
                code="INVALID_FORMAT",
                message="Ground truth file is not in valid COCO format"
            )
        
        return data
    
    def _load_coco_predictions(self, workspace: Path) -> List[Dict]:
        """加载 COCO 格式的预测结果"""
        pred_path = workspace / "output" / "pred.json"
        data = self._load_json_data(pred_path)
        
        # 验证预测格式
        if not isinstance(data, list):
            raise AutoscorerError(
                code="INVALID_FORMAT",
                message="Prediction file must be a list of detection results"
            )
        
        return data
    
    def _compute_map(self, gt_data: Dict, pred_data: List[Dict], params: Dict) -> Dict:
        """计算 mAP 指标"""
        # 获取参数
        iou_thresholds = params.get("iou_thresholds", [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95])
        area_ranges = params.get("area_ranges", [[0, 32**2], [32**2, 96**2], [96**2, float('inf')]])
        max_detections = params.get("max_detections", [1, 10, 100])
        
        # 组织数据
        gt_by_image = self._group_annotations_by_image(gt_data)
        pred_by_image = self._group_predictions_by_image(pred_data)
        
        # 计算 AP 对于每个类别和 IoU 阈值
        category_ids = [cat["id"] for cat in gt_data["categories"]]
        ap_results = {}
        
        for category_id in category_ids:
            for iou_threshold in iou_thresholds:
                ap = self._compute_ap_single_category(
                    gt_by_image, pred_by_image, 
                    category_id, iou_threshold, max_detections[-1]
                )
                ap_results[f"ap_cat_{category_id}_iou_{iou_threshold}"] = ap
        
        # 汇总结果
        map_50 = np.mean([ap_results[key] for key in ap_results if "_iou_0.5" in key])
        map_75 = np.mean([ap_results[key] for key in ap_results if "_iou_0.75" in key])
        map_overall = np.mean(list(ap_results.values()))
        
        return {
            "map": map_overall,
            "map_50": map_50,
            "map_75": map_75,
            "per_category_ap": ap_results,
            "num_categories": len(category_ids),
            "num_images": len(gt_data["images"]),
            "num_annotations": len(gt_data["annotations"]),
            "num_predictions": len(pred_data)
        }
    
    def _group_annotations_by_image(self, gt_data: Dict) -> Dict[int, List[Dict]]:
        """按图像分组标注"""
        annotations_by_image = {}
        for ann in gt_data["annotations"]:
            image_id = ann["image_id"]
            if image_id not in annotations_by_image:
                annotations_by_image[image_id] = []
            annotations_by_image[image_id].append(ann)
        return annotations_by_image
    
    def _group_predictions_by_image(self, pred_data: List[Dict]) -> Dict[int, List[Dict]]:
        """按图像分组预测"""
        predictions_by_image = {}
        for pred in pred_data:
            image_id = pred["image_id"]
            if image_id not in predictions_by_image:
                predictions_by_image[image_id] = []
            predictions_by_image[image_id].append(pred)
        return predictions_by_image
    
    def _compute_ap_single_category(self, gt_by_image, pred_by_image, category_id, iou_threshold, max_detections):
        """计算单个类别的 AP"""
        # 收集所有相关的预测和标注
        all_predictions = []
        all_annotations = []
        
        for image_id in gt_by_image:
            # 该图像的标注
            gt_anns = [ann for ann in gt_by_image[image_id] if ann["category_id"] == category_id]
            all_annotations.extend(gt_anns)
            
            # 该图像的预测
            if image_id in pred_by_image:
                pred_anns = [pred for pred in pred_by_image[image_id] if pred["category_id"] == category_id]
                # 按置信度排序，取前 max_detections 个
                pred_anns = sorted(pred_anns, key=lambda x: x["score"], reverse=True)[:max_detections]
                all_predictions.extend([(pred, image_id) for pred in pred_anns])
        
        if len(all_annotations) == 0:
            return 0.0
        
        # 按置信度排序所有预测
        all_predictions = sorted(all_predictions, key=lambda x: x[0]["score"], reverse=True)
        
        # 计算 precision-recall 曲线
        tp = np.zeros(len(all_predictions))
        fp = np.zeros(len(all_predictions))
        
        # 为每个标注创建"已匹配"标记
        gt_matched = {f"{ann['image_id']}_{i}": False for i, ann in enumerate(all_annotations)}
        
        for i, (pred, image_id) in enumerate(all_predictions):
            # 找到该图像中的所有相同类别标注
            image_gts = [ann for ann in all_annotations if ann.get("image_id") == image_id]
            
            best_iou = 0
            best_gt_idx = -1
            
            for j, gt_ann in enumerate(image_gts):
                iou = self._calculate_iou(pred["bbox"], gt_ann["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = j
            
            if best_iou >= iou_threshold:
                gt_key = f"{image_id}_{best_gt_idx}"
                if not gt_matched.get(gt_key, True):
                    tp[i] = 1
                    gt_matched[gt_key] = True
                else:
                    fp[i] = 1
            else:
                fp[i] = 1
        
        # 累积和
        tp_cumsum = np.cumsum(tp)
        fp_cumsum = np.cumsum(fp)
        
        # 计算 precision 和 recall
        precision = tp_cumsum / (tp_cumsum + fp_cumsum + 1e-8)
        recall = tp_cumsum / len(all_annotations)
        
        # 计算 AP (使用 101 点插值)
        ap = self._compute_ap_from_pr(precision, recall)
        
        return ap
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """计算两个边界框的 IoU"""
        # bbox 格式: [x, y, width, height]
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # 转换为 [x1, y1, x2, y2] 格式
        box1 = [x1, y1, x1 + w1, y1 + h1]
        box2 = [x2, y2, x2 + w2, y2 + h2]
        
        # 计算交集
        inter_x1 = max(box1[0], box2[0])
        inter_y1 = max(box1[1], box2[1])
        inter_x2 = min(box1[2], box2[2])
        inter_y2 = min(box1[3], box2[3])
        
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        
        # 计算并集
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0
    
    def _compute_ap_from_pr(self, precision: np.ndarray, recall: np.ndarray) -> float:
        """从 precision-recall 曲线计算 AP"""
        # 101 点插值方法
        recall_thresholds = np.linspace(0, 1, 101)
        interpolated_precision = np.zeros_like(recall_thresholds)
        
        for i, r in enumerate(recall_thresholds):
            # 找到 recall >= r 的所有点的最大 precision
            mask = recall >= r
            if np.any(mask):
                interpolated_precision[i] = np.max(precision[mask])
            else:
                interpolated_precision[i] = 0
        
        return np.mean(interpolated_precision)
    
    def _create_detection_result(self, map_results: Dict) -> Result:
        """创建检测结果"""
        main_score = map_results["map"]
        
        return Result(
            summary=Summary(
                score=main_score,
                rank=self._calculate_detection_rank(main_score),
                pass=main_score >= 0.5,
                message="Object detection evaluation completed"
            ),
            metrics=map_results,
            versioning={
                "scorer": self.name,
                "version": self.version,
                "algorithm": "COCO mAP Evaluation"
            }
        )
    
    def _calculate_detection_rank(self, map_score: float) -> str:
        """基于 mAP 计算等级"""
        if map_score >= 0.8:
            return "S"
        elif map_score >= 0.7:
            return "A"
        elif map_score >= 0.6:
            return "B"
        elif map_score >= 0.5:
            return "C"
        else:
            return "D"
```

## 热重载开发

### 开发环境设置

```python
# 开发模式启动 API 服务器
python -m autoscorer.api.run --reload

# 在另一个终端中加载并监控评分器文件
curl -X POST http://localhost:8000/api/v1/scorers/load \
  -H 'Content-Type: application/json' \
  -d '{
    "file_path": "custom_scorers/my_scorer.py", 
    "auto_watch": true,
    "check_interval": 1.0
  }'
```

### 热重载兼容代码

```python
# custom_scorers/my_hot_reload_scorer.py
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer

@register("my_hot_reload_scorer") 
class MyHotReloadScorer(BaseCSVScorer):
    name = "my_hot_reload_scorer"
    version = "1.0.0"  # 修改此版本号来测试热重载
    description = "支持热重载的示例评分器"
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        # 修改这里的逻辑来测试热重载效果
        return Result(
            summary={"score": 0.95, "message": "Hot reload working!"},
            metrics={"example_metric": 0.95},
            versioning={
                "scorer": self.name,
                "version": self.version,
                "reload_test": True
            }
        )

# 避免模块级全局变量，这样重载时会正确更新
if __name__ == "__main__":
    # 测试代码
    pass
```

### 热重载测试

```bash
# 测试热重载功能
curl -X POST http://localhost:8000/api/v1/scorers/test \
  -H 'Content-Type: application/json' \
  -d '{
    "scorer_name": "my_hot_reload_scorer",
    "workspace_path": "examples/classification"
  }'

# 修改 custom_scorers/my_hot_reload_scorer.py 文件
# 系统会自动检测到文件变化并重新加载

# 再次测试，应该看到新的结果
curl -X POST http://localhost:8000/api/v1/scorers/test \
  -H 'Content-Type: application/json' \
  -d '{
    "scorer_name": "my_hot_reload_scorer",
    "workspace_path": "examples/classification"
  }'
```

## 测试和验证

### 单元测试

```python
# tests/test_my_scorer.py
import pytest
import tempfile
import json
from pathlib import Path
from custom_scorers.my_scorer import MyCustomScorer

class TestMyCustomScorer:
    
    @pytest.fixture
    def temp_workspace(self):
        """创建临时测试工作区"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # 创建目录结构
            (workspace / "input").mkdir()
            (workspace / "output").mkdir()
            
            # 创建测试数据
            self._create_test_data(workspace)
            
            yield workspace
    
    def _create_test_data(self, workspace: Path):
        """创建测试数据"""
        # GT 数据
        gt_data = "id,label\n1,A\n2,B\n3,A\n4,B\n5,A\n"
        (workspace / "input" / "gt.csv").write_text(gt_data)
        
        # 预测数据
        pred_data = "id,label\n1,A\n2,A\n3,A\n4,B\n5,A\n"
        (workspace / "output" / "pred.csv").write_text(pred_data)
        
        # meta.json
        meta = {
            "job_id": "test-001",
            "task_type": "classification",
            "scorer": "my_custom_scorer"
        }
        (workspace / "meta.json").write_text(json.dumps(meta, indent=2))
    
    def test_perfect_prediction(self, temp_workspace):
        """测试完美预测情况"""
        # 修改为完美预测
        perfect_pred = "id,label\n1,A\n2,B\n3,A\n4,B\n5,A\n"
        (temp_workspace / "output" / "pred.csv").write_text(perfect_pred)
        
        scorer = MyCustomScorer()
        result = scorer.score(temp_workspace, {})
        
        assert result.summary["score"] == 1.0
        assert result.summary["pass"] == True
        assert result.metrics["accuracy"] == 1.0
    
    def test_worst_prediction(self, temp_workspace):
        """测试最差预测情况"""
        # 修改为最差预测 (完全相反)
        worst_pred = "id,label\n1,B\n2,A\n3,B\n4,A\n5,B\n"
        (temp_workspace / "output" / "pred.csv").write_text(worst_pred)
        
        scorer = MyCustomScorer()
        result = scorer.score(temp_workspace, {})
        
        assert result.summary["score"] == 0.0
        assert result.summary["pass"] == False
    
    def test_parameter_validation(self, temp_workspace):
        """测试参数验证"""
        scorer = MyCustomScorer()
        
        # 测试无效参数
        with pytest.raises(AutoscorerError) as exc_info:
            scorer.score(temp_workspace, {"invalid_param": "invalid_value"})
        
        assert exc_info.value.code == "INVALID_PARAMETER"
    
    @pytest.mark.parametrize("average_method", ["macro", "micro", "weighted"])
    def test_different_averaging_methods(self, temp_workspace, average_method):
        """测试不同平均方法"""
        scorer = MyCustomScorer()
        result = scorer.score(temp_workspace, {"average": average_method})
        
        assert "score" in result.summary
        assert result.summary["score"] >= 0
        assert result.summary["score"] <= 1
```

### 集成测试

```python
# tests/test_scorer_integration.py
import requests
import time

def test_scorer_api_integration():
    """测试评分器 API 集成"""
    base_url = "http://localhost:8000"
    
    # 1. 检查评分器是否已注册
    response = requests.get(f"{base_url}/api/v1/scorers")
    assert response.status_code == 200
    
    scorers = response.json()["data"]
    scorer_names = [s["name"] for s in scorers]
    assert "my_custom_scorer" in scorer_names
    
    # 2. 测试评分器
    response = requests.post(f"{base_url}/api/v1/scorers/my_custom_scorer/test", json={
        "workspace_path": "examples/classification"
    })
    assert response.status_code == 200
    
    result = response.json()["data"]
    assert "result" in result
    assert "summary" in result["result"]
    assert "score" in result["result"]["summary"]
```

## 最佳实践

### 1. 错误处理

```python
from autoscorer.utils.errors import AutoscorerError

def robust_scorer_method(self, data):
    """健壮的评分器方法示例"""
    try:
        # 核心逻辑
        result = self._compute_complex_metric(data)
        return result
        
    except FileNotFoundError as e:
        raise AutoscorerError(
            code="MISSING_FILE",
            message=f"Required file not found: {e.filename}",
            details={"file_path": str(e.filename)}
        )
    except ValueError as e:
        raise AutoscorerError(
            code="INVALID_DATA",
            message=f"Data validation failed: {str(e)}",
            details={"validation_error": str(e)}
        )
    except Exception as e:
        # 捕获意外错误
        raise AutoscorerError(
            code="UNEXPECTED_ERROR",
            message=f"Unexpected error in {self.name}: {str(e)}",
            details={
                "scorer": self.name,
                "version": self.version,
                "error_type": type(e).__name__
            }
        )
```

### 2. 性能优化

```python
import time
import psutil
from functools import wraps

def performance_monitor(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            result = func(self, *args, **kwargs)
            
            # 添加性能信息到结果
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            if hasattr(result, 'timing'):
                result.timing.update({
                    'execution_time': end_time - start_time,
                    'memory_delta': end_memory - start_memory
                })
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Method {func.__name__} failed after {execution_time:.2f}s")
            raise
    
    return wrapper

class OptimizedScorer(BaseScorer):
    
    @performance_monitor
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        """带性能监控的评分方法"""
        # 评分逻辑
        pass
```

### 3. 日志和调试

```python
import logging
from autoscorer.utils.logger import get_logger

class DebuggableScorer(BaseScorer):
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        self.logger.info(f"Starting evaluation with scorer {self.name} v{self.version}")
        self.logger.debug(f"Parameters: {params}")
        
        try:
            # 数据加载
            self.logger.info("Loading ground truth and predictions")
            gt_data = self._load_ground_truth(workspace)
            pred_data = self._load_predictions(workspace)
            self.logger.info(f"Loaded {len(gt_data)} ground truth and {len(pred_data)} prediction items")
            
            # 评分计算
            self.logger.info("Computing metrics")
            metrics = self._compute_metrics(gt_data, pred_data, params)
            self.logger.info(f"Computed metrics: {list(metrics.keys())}")
            
            # 结果创建
            result = self._create_result(metrics)
            self.logger.info(f"Evaluation completed successfully. Score: {result.summary['score']}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Evaluation failed: {e}", exc_info=True)
            raise
```

### 4. 配置化设计

```python
class ConfigurableScorer(BaseScorer):
    """支持配置化的评分器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "threshold": 0.5,
            "average_method": "macro",
            "enable_artifacts": True,
            "output_precision": 4
        }
        
        if config_path and Path(config_path).exists():
            import yaml
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            # 合并配置
            return {**default_config, **user_config}
        
        return default_config
    
    def score(self, workspace: Path, params: Dict[str, Any]) -> Result:
        # 合并配置和参数
        effective_params = {**self.config, **params}
        
        # 使用合并后的参数进行评分
        return self._score_with_params(workspace, effective_params)
```

### 5. 文档和类型注解

```python
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path

class WellDocumentedScorer(BaseScorer):
    """
    完整文档的评分器示例
    
    这个评分器展示了如何编写清晰的文档和类型注解。
    支持多种评分策略和参数配置。
    
    Attributes:
        name: 评分器唯一标识符
        version: 语义化版本号  
        description: 功能描述
        supported_strategies: 支持的评分策略列表
    
    Example:
        >>> scorer = WellDocumentedScorer()
        >>> result = scorer.score(workspace, {"strategy": "advanced"})
        >>> print(f"Score: {result.summary['score']}")
    """
    
    name = "well_documented_scorer"
    version = "1.0.0"
    description = "示例评分器，展示最佳实践"
    
    def score(
        self, 
        workspace: Path, 
        params: Dict[str, Any]
    ) -> Result:
        """
        执行评分计算
        
        Args:
            workspace: 工作区路径，必须包含以下结构:
                - input/gt.csv: 标准答案文件
                - output/pred.csv: 预测结果文件
            params: 评分参数字典，支持以下参数:
                - strategy (str): 评分策略 ('basic'|'advanced')
                - threshold (float): 决策阈值，范围 [0, 1]
                - weights (Dict[str, float]): 类别权重映射
        
        Returns:
            Result: 包含以下字段的评分结果:
                - summary.score: 主要评分 (float)
                - summary.rank: 等级评价 (str)
                - summary.pass: 是否通过 (bool)
                - metrics: 详细指标字典
                - timing: 执行时间统计
                - versioning: 版本信息
        
        Raises:
            AutoscorerError: 当工作区格式不正确或评分失败时
            
        Example:
            >>> workspace = Path("/path/to/workspace")
            >>> params = {"strategy": "advanced", "threshold": 0.7}
            >>> result = scorer.score(workspace, params)
            >>> assert result.summary["score"] >= 0
        """
        # 实现细节...
        pass
    
    def _validate_parameters(
        self, 
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        验证输入参数的有效性
        
        Args:
            params: 待验证的参数字典
            
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误消息)
        """
        # 验证逻辑...
        pass
```

## 相关文档

- **[工作区规范](workspace-spec.md)** - 了解数据格式要求
- **[API 参考](api-reference.md)** - 程序化调用评分器
- **[配置管理](configuration.md)** - 评分器配置选项
- **[输出标准](output-standards.md)** - 结果格式规范
- **[开发指南](development.md)** - 开发环境和调试技巧
