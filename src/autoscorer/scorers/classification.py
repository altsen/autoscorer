from __future__ import annotations
from pathlib import Path
from typing import Dict
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
import json
from collections import defaultdict


def _make_classification_artifacts(ws: Path, gt_rows: Dict[str, Dict[str, str]], pred_rows: Dict[str, Dict[str, str]], metrics: Dict[str, float]):
    """生成分类任务的工件：
    - confusion_matrix.json（labels与矩阵）
    - error_cases.csv（错误样本清单）
    - confusion_matrix.png（如可用的可视化，软依赖matplotlib）
    """
    out_dir = ws / "output" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 统一标签表
    labels = sorted(set(row["label"] for row in gt_rows.values()))
    idx = {lbl: i for i, lbl in enumerate(labels)}
    # 混淆矩阵
    n = len(labels)
    cm = [[0 for _ in range(n)] for _ in range(n)]
    errors = []
    for _id, gt in gt_rows.items():
        g = gt["label"]
        p = pred_rows[_id]["label"]
        cm[idx[g]][idx[p]] += 1
        if g != p:
            errors.append((_id, g, p))

    # 写入 confusion_matrix.json
    (out_dir / "confusion_matrix.json").write_text(
        json.dumps({"labels": labels, "matrix": cm, "metrics": metrics}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 error_cases.csv
    import csv
    with (out_dir / "error_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "gt", "pred"]) 
        w.writerows(errors)

    # 可选：绘制混淆矩阵图（软依赖）
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        fig, ax = plt.subplots(figsize=(max(4, n), max(3, n)))
        im = ax.imshow(np.array(cm), cmap="Blues")
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticklabels(labels)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Ground Truth")
        for i in range(n):
            for j in range(n):
                ax.text(j, i, str(cm[i][j]), ha="center", va="center", color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(out_dir / "confusion_matrix.png", dpi=150)
        plt.close(fig)
    except Exception:
        # 忽略绘图失败（未安装matplotlib或环境不支持）
        pass


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
            
            # 4. 特征工件
            _make_classification_artifacts(ws, gt_data, pred_data, metrics)
            # 5. 标准化summary - 分类算法主评分为f1_macro
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
            
            # 6. 返回标准化结果
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

    # 新增：评分器自校验
    def validate(self, workspace: Path, params: Dict) -> None:
        ws = Path(workspace)
        gt_path = ws / "input" / "gt.csv"
        pred_path = ws / "output" / "pred.csv"
        gt = self._load_and_validate_csv(gt_path, ["id", "label"])
        pred = self._load_and_validate_csv(pred_path, ["id", "label"])
        self._validate_data_consistency(gt, pred)
    
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

            # 4. 特征工件
            _make_classification_artifacts(ws, gt_data, pred_data, metrics)

            # 5. 标准化summary - 分类算法主评分为accuracy
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
            
            # 6. 返回标准化结果
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

    # 新增：评分器自校验
    def validate(self, workspace: Path, params: Dict) -> None:
        ws = Path(workspace)
        gt_path = ws / "input" / "gt.csv"
        pred_path = ws / "output" / "pred.csv"
        gt = self._load_and_validate_csv(gt_path, ["id", "label"])
        pred = self._load_and_validate_csv(pred_path, ["id", "label"])
        self._validate_data_consistency(gt, pred)
    
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
