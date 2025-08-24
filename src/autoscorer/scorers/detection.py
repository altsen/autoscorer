from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any
import json
from autoscorer.schemas.result import Result
from autoscorer.utils.errors import AutoscorerError
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer


@register("detection_map")
class DetectionMAP(BaseCSVScorer):
    """目标检测mAP评分器 - 基础实现
    
    注意：这是一个简化的mAP计算实现，生产环境建议使用：
    - pycocotools (COCO格式)
    - Detectron2的评估工具
    - YOLOv5/YOLOv8的评估模块
    """
    
    name = "detection_map"
    version = "2.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        """mAP计算主入口"""
        ws = Path(workspace)
        
        try:
            # 1. 加载和校验数据
            gt_data = self._load_ground_truth(ws)
            pred_data = self._load_predictions(ws)
            
            # 2. 数据格式校验
            self._validate_detection_data(gt_data, pred_data)
            
            # 3. 计算mAP指标
            metrics = self._compute_map_metrics(gt_data, pred_data, params)
            
            # 4. 标准化summary - 检测算法主评分为mAP
            map_score = metrics["mAP"]
            summary = {
                "score": map_score,  # 标准主评分字段
                "mAP": map_score,    # 算法特定字段保持兼容性
            }
            
            # 添加等级评定
            if map_score >= 0.7:
                summary["rank"] = "A"
            elif map_score >= 0.5:
                summary["rank"] = "B"
            elif map_score >= 0.3:
                summary["rank"] = "C"
            else:
                summary["rank"] = "D"
                
            # 添加通过标准(可配置)
            threshold = params.get("pass_threshold", 0.5)
            summary["pass"] = map_score >= threshold
            
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
                    "algorithm": "Mean Average Precision (simplified)",
                    "timestamp": self._get_iso_timestamp()
                }
            )
            
        except AutoscorerError:
            raise
        except Exception as e:
            raise AutoscorerError(
                code="SCORE_ERROR",
                message=f"mAP calculation failed: {str(e)}",
                details={"algorithm": self.name, "version": self.version}
            )
    
    def _load_ground_truth(self, workspace: Path) -> List[Dict]:
        """加载标准答案JSON"""
        gt_path = workspace / "input" / "gt.json"
        return self._load_and_validate_json(gt_path, "ground truth")
    
    def _load_predictions(self, workspace: Path) -> List[Dict]:
        """加载模型预测JSON"""
        pred_path = workspace / "output" / "pred.json"
        return self._load_and_validate_json(pred_path, "predictions")
    
    def _load_and_validate_json(self, path: Path, data_type: str) -> List[Dict]:
        """加载和校验JSON文件"""
        if not path.exists():
            raise AutoscorerError(code="MISSING_FILE", message=f"File not found: {path}")
        
        try:
            with path.open('r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"{data_type} must be a JSON array: {path}"
                )
            
            return data
            
        except json.JSONDecodeError as e:
            raise AutoscorerError(
                code="PARSE_ERROR", 
                message=f"JSON parsing failed for {path}: {e}"
            )
        except UnicodeDecodeError:
            raise AutoscorerError(
                code="BAD_FORMAT", 
                message=f"File encoding error, must be UTF-8: {path}"
            )
        except Exception as e:
            raise AutoscorerError(
                code="PARSE_ERROR", 
                message=f"Error loading {data_type} from {path}: {e}"
            )
    
    def _validate_detection_data(self, gt_data: List[Dict], pred_data: List[Dict]):
        """验证检测数据格式"""
        # 检查GT格式
        required_gt_fields = ["image_id", "bbox", "category_id"]
        for i, item in enumerate(gt_data[:5]):  # 只检查前5个
            if not isinstance(item, dict):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"GT item {i} must be an object"
                )
            
            for field in required_gt_fields:
                if field not in item:
                    raise AutoscorerError(
                        code="BAD_FORMAT",
                        message=f"GT item {i} missing field: {field}"
                    )
            
            # 检查bbox格式 [x, y, width, height]
            bbox = item["bbox"]
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"GT item {i} bbox must be [x, y, width, height]"
                )
        
        # 检查预测格式
        required_pred_fields = ["image_id", "bbox", "category_id", "score"]
        for i, item in enumerate(pred_data[:5]):  # 只检查前5个
            if not isinstance(item, dict):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Prediction item {i} must be an object"
                )
            
            for field in required_pred_fields:
                if field not in item:
                    raise AutoscorerError(
                        code="BAD_FORMAT",
                        message=f"Prediction item {i} missing field: {field}"
                    )
            
            # 检查bbox格式
            bbox = item["bbox"]
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Prediction item {i} bbox must be [x, y, width, height]"
                )
            
            # 检查置信度分数
            try:
                score = float(item["score"])
                if not (0 <= score <= 1):
                    raise AutoscorerError(
                        code="BAD_FORMAT",
                        message=f"Prediction item {i} score must be between 0 and 1: {score}"
                    )
            except (ValueError, TypeError):
                raise AutoscorerError(
                    code="BAD_FORMAT",
                    message=f"Prediction item {i} score must be a number: {item['score']}"
                )
    
    def _compute_map_metrics(self, gt_data: List[Dict], pred_data: List[Dict], params: Dict) -> Dict[str, float]:
        """计算mAP指标 (简化实现)
        
        注意：这是一个简化的mAP计算，仅用于演示。
        生产环境应该使用专业的评估库如 pycocotools。
        """
        
        # 参数
        iou_threshold = params.get("iou_threshold", 0.5)
        score_threshold = params.get("score_threshold", 0.0)
        
        # 按图像组织数据
        gt_by_image = {}
        pred_by_image = {}
        
        for item in gt_data:
            image_id = item["image_id"]
            if image_id not in gt_by_image:
                gt_by_image[image_id] = []
            gt_by_image[image_id].append(item)
        
        for item in pred_data:
            if item["score"] >= score_threshold:  # 过滤低置信度
                image_id = item["image_id"]
                if image_id not in pred_by_image:
                    pred_by_image[image_id] = []
                pred_by_image[image_id].append(item)
        
        # 获取所有类别
        gt_categories = set(item["category_id"] for item in gt_data)
        pred_categories = set(item["category_id"] for item in pred_data)
        all_categories = gt_categories.union(pred_categories)
        
        # 计算每个类别的AP
        aps = []
        category_metrics = {}
        
        for category_id in all_categories:
            ap = self._compute_ap_for_category(
                gt_by_image, pred_by_image, category_id, iou_threshold
            )
            aps.append(ap)
            category_metrics[f"AP_class_{category_id}"] = ap
        
        # 计算mAP
        map_score = sum(aps) / len(aps) if aps else 0.0
        
        # 统计信息
        total_gt = len(gt_data)
        total_pred = len([item for item in pred_data if item["score"] >= score_threshold])
        
        metrics = {
            "mAP": map_score,
            "num_categories": len(all_categories),
            "total_gt_boxes": float(total_gt),
            "total_pred_boxes": float(total_pred),
            "iou_threshold": iou_threshold,
            "score_threshold": score_threshold,
            **category_metrics
        }
        
        return metrics
    
    def _compute_ap_for_category(self, gt_by_image: Dict, pred_by_image: Dict, 
                                category_id: int, iou_threshold: float) -> float:
        """计算单个类别的AP (简化实现)"""
        
        # 收集该类别的所有GT和预测
        gt_boxes = []
        pred_boxes = []
        
        for image_id in gt_by_image:
            for gt in gt_by_image[image_id]:
                if gt["category_id"] == category_id:
                    gt_boxes.append((image_id, gt["bbox"]))
        
        for image_id in pred_by_image:
            for pred in pred_by_image[image_id]:
                if pred["category_id"] == category_id:
                    pred_boxes.append((image_id, pred["bbox"], pred["score"]))
        
        if not gt_boxes:
            return 0.0  # 没有GT，AP为0
        
        if not pred_boxes:
            return 0.0  # 没有预测，AP为0
        
        # 按置信度排序预测
        pred_boxes.sort(key=lambda x: x[2], reverse=True)
        
        # 计算precision和recall
        tp = 0
        fp = 0
        matched_gt = set()
        
        precisions = []
        recalls = []
        
        for pred_image_id, pred_bbox, pred_score in pred_boxes:
            # 查找最佳匹配的GT
            best_iou = 0
            best_gt_idx = -1
            
            for i, (gt_image_id, gt_bbox) in enumerate(gt_boxes):
                if gt_image_id == pred_image_id and i not in matched_gt:
                    iou = self._compute_iou(pred_bbox, gt_bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = i
            
            if best_iou >= iou_threshold:
                tp += 1
                matched_gt.add(best_gt_idx)
            else:
                fp += 1
            
            precision = tp / (tp + fp)
            recall = tp / len(gt_boxes)
            
            precisions.append(precision)
            recalls.append(recall)
        
        # 计算AP (简化为precision的平均值)
        if precisions:
            return sum(precisions) / len(precisions)
        else:
            return 0.0
    
    def _compute_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """计算两个边界框的IoU"""
        try:
            # bbox格式: [x, y, width, height]
            x1, y1, w1, h1 = bbox1
            x2, y2, w2, h2 = bbox2
            
            # 转换为 [x1, y1, x2, y2] 格式
            x1_max = x1 + w1
            y1_max = y1 + h1
            x2_max = x2 + w2
            y2_max = y2 + h2
            
            # 计算交集
            inter_x1 = max(x1, x2)
            inter_y1 = max(y1, y2)
            inter_x2 = min(x1_max, x2_max)
            inter_y2 = min(y1_max, y2_max)
            
            if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
                return 0.0
            
            inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
            area1 = w1 * h1
            area2 = w2 * h2
            union_area = area1 + area2 - inter_area
            
            if union_area <= 0:
                return 0.0
            
            return inter_area / union_area
            
        except Exception:
            return 0.0
