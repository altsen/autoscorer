from __future__ import annotations
from pathlib import Path
from typing import Dict
import csv
from datetime import datetime, timezone
from autoscorer.utils.errors import AutoscorerError


class BaseCSVScorer:
    """CSV格式评分器基类，提供通用的CSV数据处理"""
    
    def _get_iso_timestamp(self) -> str:
        """获取ISO格式时间戳"""
        return datetime.now(timezone.utc).isoformat()
    
    def _load_and_validate_csv(self, path: Path, required_columns: list) -> Dict[str, str]:
        """加载和校验CSV文件"""
        if not path.exists():
            raise AutoscorerError(code="MISSING_FILE", message=f"File not found: {path}")
        
        try:
            data = {}
            with path.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # 检查必需列
                if not reader.fieldnames:
                    raise AutoscorerError(
                        code="BAD_FORMAT",
                        message=f"CSV file has no header: {path}"
                    )
                
                missing_cols = set(required_columns) - set(reader.fieldnames)
                if missing_cols:
                    raise AutoscorerError(
                        code="BAD_FORMAT",
                        message=f"Missing columns in {path}: {list(missing_cols)}"
                    )
                
                # 加载数据并检查重复ID
                for i, row in enumerate(reader):
                    row_id = row.get('id')
                    if not row_id:
                        raise AutoscorerError(
                            code="BAD_FORMAT",
                            message=f"Missing ID in row {i+2} of {path}"  # +2 for header and 1-based
                        )
                    
                    if row_id in data:
                        raise AutoscorerError(
                            code="MISMATCH",
                            message=f"Duplicate ID in {path}: {row_id}"
                        )
                    
                    data[row_id] = row
            
            if not data:
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"CSV file contains no data rows: {path}"
                )
            
            return data
            
        except UnicodeDecodeError:
            raise AutoscorerError(
                code="BAD_FORMAT", 
                message=f"File encoding error, must be UTF-8: {path}"
            )
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="PARSE_ERROR", 
                message=f"CSV parsing failed for {path}: {e}"
            )
    
    def _validate_id_consistency(self, gt_data: Dict, pred_data: Dict):
        """验证GT和预测数据的ID一致性"""
        gt_ids = set(gt_data.keys())
        pred_ids = set(pred_data.keys())
        
        if gt_ids != pred_ids:
            missing_in_pred = gt_ids - pred_ids
            extra_in_pred = pred_ids - gt_ids
            
            error_details = []
            if missing_in_pred:
                error_details.append(f"Missing in predictions: {sorted(list(missing_in_pred))[:5]}")
            if extra_in_pred:
                error_details.append(f"Extra in predictions: {sorted(list(extra_in_pred))[:5]}")
            
            raise AutoscorerError(
                code="MISMATCH",
                message=f"ID mismatch between GT and predictions. {'; '.join(error_details)}",
                details={
                    "gt_count": len(gt_ids),
                    "pred_count": len(pred_ids),
                    "missing_in_pred": len(missing_in_pred),
                    "extra_in_pred": len(extra_in_pred)
                }
            )
