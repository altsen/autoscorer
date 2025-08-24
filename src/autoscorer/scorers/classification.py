from __future__ import annotations
from pathlib import Path
from typing import Dict
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer


@register("classification_f1")
class ClassificationF1(BaseCSVScorer):
    """分类F1评分器 - 标准化版本"""
    
    name = "classification_f1"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """F1分数计算主入口"""
        ws = Path(workspace)
        
        try:
            # 1. 加载和校验数据
            gt_data = self._load_ground_truth(ws)
            pred_data = self._load_predictions(ws)
            
            # 2. 数据一致性校验
            self._validate_data_consistency(gt_data, pred_data)
            
            # 3. 计算F1指标
            metrics = self._compute_f1_metrics(gt_data, pred_data)
            
            # 4. 标准化summary - 分类算法主评分为f1_macro
            f1_score = metrics["f1_macro"]
            summary = {
                "score": f1_score,  # 标准主评分字段
                "f1_macro": f1_score,  # 算法特定字段保持兼容性
            }
            
            # 添加等级评定
            if f1_score >= 0.9:
                summary["rank"] = "A"
            elif f1_score >= 0.8:
                summary["rank"] = "B" 
            elif f1_score >= 0.7:
                summary["rank"] = "C"
            else:
                summary["rank"] = "D"
                
            # 添加通过标准(可配置)
            threshold = params.get("pass_threshold", 0.8)
            summary["pass"] = f1_score >= threshold
            
            # 5. 返回标准化结果
            return Result(
                summary=summary,
                metrics=metrics,
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name, 
                    "version": self.version,
                    "algorithm": "F1-Score Macro Average",
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
    
    def _load_ground_truth(self, workspace: Path) -> Dict[str, str]:
        """加载标准答案"""
        gt_path = workspace / "input" / "gt.csv"
        return self._load_and_validate_csv(gt_path, ["id", "label"])
    
    def _load_predictions(self, workspace: Path) -> Dict[str, str]:
        """加载模型预测"""
        pred_path = workspace / "output" / "pred.csv"
        return self._load_and_validate_csv(pred_path, ["id", "label"])
    
    def _validate_data_consistency(self, gt_data: Dict, pred_data: Dict):
        """验证数据一致性"""
        # ID一致性检查
        self._validate_id_consistency(gt_data, pred_data)
        
        # 标签格式检查（分类任务允许任意字符串标签）
        for row_id, row in gt_data.items():
            if not row["label"].strip():
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Empty label in GT for ID: {row_id}"
                )
        
        for row_id, row in pred_data.items():
            if not row["label"].strip():
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Empty label in predictions for ID: {row_id}"
                )
    
    def _compute_f1_metrics(self, gt_data: Dict, pred_data: Dict) -> Dict[str, float]:
        """计算F1指标"""
        # 提取标签
        gt_labels = {k: v["label"] for k, v in gt_data.items()}
        pred_labels = {k: v["label"] for k, v in pred_data.items()}
        
        # 获取所有唯一标签（基于GT）
        unique_labels = sorted(set(gt_labels.values()))
        
        # 计算每个标签的F1
        per_label_f1 = {}
        for label in unique_labels:
            tp = sum(1 for k in gt_labels if gt_labels[k] == label and pred_labels[k] == label)
            fp = sum(1 for k in pred_labels if pred_labels[k] == label and gt_labels[k] != label)
            fn = sum(1 for k in gt_labels if gt_labels[k] == label and pred_labels[k] != label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            per_label_f1[f"f1_{label}"] = f1
        
        # 计算macro-F1
        macro_f1 = sum(per_label_f1.values()) / len(unique_labels) if unique_labels else 0.0
        
        # 返回所有指标
        metrics = {
            "f1_macro": macro_f1,
            "num_labels": len(unique_labels),
            "total_samples": len(gt_labels),
            **per_label_f1
        }
        
        return metrics


@register("classification_accuracy")
class ClassificationAccuracy(BaseCSVScorer):
    """分类准确率评分器 - 标准化版本"""
    
    name = "classification_accuracy"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """准确率计算主入口"""
        ws = Path(workspace)
        
        try:
            # 1. 加载和校验数据
            gt_data = self._load_ground_truth(ws)
            pred_data = self._load_predictions(ws)
            
            # 2. 数据一致性校验
            self._validate_data_consistency(gt_data, pred_data)
            
            # 3. 计算准确率指标
            metrics = self._compute_accuracy_metrics(gt_data, pred_data)
            
            # 4. 标准化summary - 分类算法主评分为accuracy
            accuracy = metrics["accuracy"]
            summary = {
                "score": accuracy,  # 标准主评分字段
                "accuracy": accuracy,  # 算法特定字段保持兼容性
            }
            
            # 添加等级评定
            if accuracy >= 0.95:
                summary["rank"] = "A"
            elif accuracy >= 0.85:
                summary["rank"] = "B"
            elif accuracy >= 0.75:
                summary["rank"] = "C"
            else:
                summary["rank"] = "D"
                
            # 添加通过标准(可配置)
            threshold = params.get("pass_threshold", 0.8)
            summary["pass"] = accuracy >= threshold
            
            # 5. 返回标准化结果
            return Result(
                summary=summary,
                metrics=metrics,
                artifacts={},
                timing={},
                resources={},
                versioning={
                    "scorer": self.name, 
                    "version": self.version,
                    "algorithm": "Classification Accuracy",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"Accuracy calculation failed: {str(e)}",
                details={"algorithm": self.name, "version": self.version}
            )
    
    def _load_ground_truth(self, workspace: Path) -> Dict[str, str]:
        """加载标准答案"""
        gt_path = workspace / "input" / "gt.csv"
        return self._load_and_validate_csv(gt_path, ["id", "label"])
    
    def _load_predictions(self, workspace: Path) -> Dict[str, str]:
        """加载模型预测"""
        pred_path = workspace / "output" / "pred.csv"
        return self._load_and_validate_csv(pred_path, ["id", "label"])
    
    def _validate_data_consistency(self, gt_data: Dict, pred_data: Dict):
        """验证数据一致性"""
        # ID一致性检查
        self._validate_id_consistency(gt_data, pred_data)
        
        # 标签格式检查
        for row_id, row in gt_data.items():
            if not row["label"].strip():
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Empty label in GT for ID: {row_id}"
                )
        
        for row_id, row in pred_data.items():
            if not row["label"].strip():
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Empty label in predictions for ID: {row_id}"
                )
    
    def _compute_accuracy_metrics(self, gt_data: Dict, pred_data: Dict) -> Dict[str, float]:
        """计算准确率指标"""
        # 提取标签
        gt_labels = {k: v["label"] for k, v in gt_data.items()}
        pred_labels = {k: v["label"] for k, v in pred_data.items()}
        
        # 计算准确率
        correct = sum(1 for k in gt_labels if gt_labels[k] == pred_labels[k])
        total = len(gt_labels)
        accuracy = correct / total if total > 0 else 0.0
        
        # 计算每类准确率
        unique_labels = sorted(set(gt_labels.values()))
        per_class_acc = {}
        
        for label in unique_labels:
            label_ids = [k for k, v in gt_labels.items() if v == label]
            label_correct = sum(1 for k in label_ids if pred_labels[k] == label)
            label_total = len(label_ids)
            per_class_acc[f"acc_{label}"] = label_correct / label_total if label_total > 0 else 0.0
        
        # 返回所有指标
        metrics = {
            "accuracy": accuracy,
            "correct": float(correct),
            "total": float(total),
            "num_classes": len(unique_labels),
            **per_class_acc
        }
        
        return metrics
