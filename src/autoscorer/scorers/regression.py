from __future__ import annotations
from pathlib import Path
from typing import Dict
import math
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
import json


@register("regression_rmse")
class RegressionRMSE(BaseCSVScorer):
    """回归RMSE评分器 - 标准化版本"""
    
    name = "regression_rmse"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """RMSE计算主入口"""
        ws = Path(workspace)
        
        try:
            # 1. 加载和校验数据
            gt_data = self._load_ground_truth(ws)
            pred_data = self._load_predictions(ws)
            
            # 2. 数据一致性校验
            self._validate_data_consistency(gt_data, pred_data)
            
            # 3. 计算RMSE指标
            metrics = self._compute_rmse_metrics(gt_data, pred_data)
            # 3.1 工件：残差与散点（CSV/可选PNG）
            self._make_regression_artifacts(ws, gt_data, pred_data, metrics)
            
            # 4. 标准化summary - 回归算法主评分为rmse (注意：越小越好)
            rmse = metrics["rmse"]
            summary = {
                "score": rmse,  # 标准主评分字段，对于RMSE越小越好
                "rmse": rmse,  # 算法特定字段保持兼容性
            }
            
            # 添加等级评定 (基于RMSE阈值，可根据具体问题调整)
            if rmse <= 0.1:
                summary["rank"] = "A"
            elif rmse <= 0.3:
                summary["rank"] = "B"
            elif rmse <= 0.5:
                summary["rank"] = "C"
            else:
                summary["rank"] = "D"
                
            # 添加通过标准(可配置) - 对于RMSE，小于阈值为通过
            threshold = params.get("pass_threshold", 0.5)
            summary["pass"] = rmse <= threshold
            
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
                    "algorithm": "Root Mean Square Error",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"RMSE calculation failed: {str(e)}",
                details={"algorithm": self.name, "version": self.version}
            )
    
    def _load_ground_truth(self, workspace: Path) -> Dict[str, float]:
        """加载标准答案"""
        gt_path = workspace / "input" / "gt.csv"
        raw_data = self._load_and_validate_csv(gt_path, ["id", "label"])
        return self._convert_to_numeric(raw_data, "GT")
    
    def _load_predictions(self, workspace: Path) -> Dict[str, float]:
        """加载模型预测"""
        pred_path = workspace / "output" / "pred.csv"
        raw_data = self._load_and_validate_csv(pred_path, ["id", "label"])
        return self._convert_to_numeric(raw_data, "predictions")
    
    def _convert_to_numeric(self, data: Dict, data_type: str) -> Dict[str, float]:
        """转换标签为数值类型"""
        numeric_data = {}
        for row_id, row in data.items():
            try:
                numeric_data[row_id] = float(row["label"])
            except (ValueError, TypeError):
                raise AutoscorerError(
                    code="TYPE_ERROR",
                    message=f"Label cannot be converted to float in {data_type} for ID {row_id}: '{row['label']}'"
                )
        return numeric_data
    
    def _validate_data_consistency(self, gt_data: Dict, pred_data: Dict):
        """验证数据一致性"""
        # ID一致性检查
        self._validate_id_consistency(gt_data, pred_data)
        
        # 数值有效性检查
        for row_id, value in gt_data.items():
            if math.isnan(value) or math.isinf(value):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Invalid numeric value in GT for ID {row_id}: {value}"
                )
        
        for row_id, value in pred_data.items():
            if math.isnan(value) or math.isinf(value):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Invalid numeric value in predictions for ID {row_id}: {value}"
                )
    
    def _compute_rmse_metrics(self, gt_data: Dict, pred_data: Dict) -> Dict[str, float]:
        """计算RMSE指标"""
        
        # 计算各种回归指标
        n = len(gt_data)
        se_sum = 0.0  # 平方误差和
        ae_sum = 0.0  # 绝对误差和
        gt_sum = 0.0  # GT值和
        pred_sum = 0.0  # 预测值和
        
        for row_id in gt_data:
            gt_val = gt_data[row_id]
            pred_val = pred_data[row_id]
            
            se_sum += (pred_val - gt_val) ** 2
            ae_sum += abs(pred_val - gt_val)
            gt_sum += gt_val
            pred_sum += pred_val
        
        # 基础指标
        mse = se_sum / n if n > 0 else 0.0
        rmse = math.sqrt(mse)
        mae = ae_sum / n if n > 0 else 0.0
        
        # 均值
        gt_mean = gt_sum / n if n > 0 else 0.0
        pred_mean = pred_sum / n if n > 0 else 0.0
        
        # R²计算
        ss_tot = sum((gt_data[k] - gt_mean) ** 2 for k in gt_data)
        r_squared = 1 - (se_sum / ss_tot) if ss_tot > 0 else 0.0
        
        # 返回所有指标
        metrics = {
            "rmse": rmse,
            "mse": mse,
            "mae": mae,
            "r_squared": r_squared,
            "gt_mean": gt_mean,
            "pred_mean": pred_mean,
            "n_samples": float(n)
        }
        
        return metrics

    def _make_regression_artifacts(self, ws: Path, gt: Dict[str, float], pred: Dict[str, float], metrics: Dict[str, float]):
        out_dir = ws / "output" / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        # 残差文件
        import csv
        rows = []
        for k in gt:
            rows.append((k, gt[k], pred[k], pred[k] - gt[k]))
        with (out_dir / "residuals.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "gt", "pred", "residual"])
            w.writerows(rows)
        # 汇总指标
        (out_dir / "summary.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 可选绘图
        try:
            import matplotlib.pyplot as plt  # type: ignore
            xs = list(range(len(rows)))
            res = [r[3] for r in rows]
            plt.figure(figsize=(6,3))
            plt.plot(xs, res, marker='o', linestyle='-')
            plt.title('Residuals')
            plt.xlabel('index')
            plt.ylabel('residual')
            plt.tight_layout()
            plt.savefig(out_dir / 'residuals.png', dpi=150)
            plt.close()
        except Exception:
            pass
