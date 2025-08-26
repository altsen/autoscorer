from pathlib import Path
import json
import os
from autoscorer.utils.errors import AutoscorerError


def validate_workspace(ws: Path) -> dict:
    """校验标准工作区结构和 meta.json 合规性。"""
    result = {"ok": True, "errors": []}
    
    # 检查必需目录和文件
    required_paths = {
        "input": {"type": "dir", "required": True},
        "meta.json": {"type": "file", "required": True},
        "output": {"type": "dir", "required": False},  # 可自动创建
        "logs": {"type": "dir", "required": False}     # 可自动创建
    }
    
    for name, config in required_paths.items():
        path = ws / name
        
        if config["required"] and not path.exists():
            result["ok"] = False
            result["errors"].append(f"MISSING_FILE: {name}")
        elif path.exists():
            # 检查权限
            if config["type"] == "dir":
                if not os.access(path, os.R_OK):
                    result["ok"] = False
                    result["errors"].append(f"PERMISSION_ERROR: {name} not readable")
                if name in ["output", "logs"] and not os.access(path, os.W_OK):
                    result["ok"] = False
                    result["errors"].append(f"PERMISSION_ERROR: {name} not writable")
            elif config["type"] == "file" and not os.access(path, os.R_OK):
                result["ok"] = False
                result["errors"].append(f"PERMISSION_ERROR: {name} not readable")
        elif not config["required"]:
            # 检查可创建性
            try:
                path.mkdir(parents=True, exist_ok=True)
                if not os.access(path, os.W_OK):
                    result["ok"] = False
                    result["errors"].append(f"PERMISSION_ERROR: cannot create writable {name}")
            except Exception as e:
                result["ok"] = False
                result["errors"].append(f"PERMISSION_ERROR: cannot create {name}: {e}")
    
    # 验证 meta.json 内容
    try:
        meta_path = ws / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            
            # 检查必需字段
            required_fields = ["job_id", "task_type", "scorer", "input_uri", "output_uri"]
            for field in required_fields:
                if field not in meta:
                    result["ok"] = False
                    result["errors"].append(f"BAD_FORMAT: meta.json missing field: {field}")
            
            # 检查资源配置合理性
            if "resources" in meta:
                resources = meta["resources"]
                if "cpu" in resources:
                    try:
                        cpu = float(resources["cpu"])
                        if cpu <= 0:
                            result["ok"] = False
                            result["errors"].append("INVALID_RESOURCES: cpu must be > 0")
                    except (ValueError, TypeError):
                        result["ok"] = False
                        result["errors"].append("INVALID_RESOURCES: cpu must be a number")
                
                if "memory" in resources:
                    memory = str(resources["memory"])
                    if not _validate_memory_format(memory):
                        result["ok"] = False
                        result["errors"].append(f"INVALID_RESOURCES: invalid memory format: {memory}")
                
                if "gpus" in resources:
                    try:
                        gpus = int(resources["gpus"])
                        if gpus < 0:
                            result["ok"] = False
                            result["errors"].append("INVALID_RESOURCES: gpus must be >= 0")
                    except (ValueError, TypeError):
                        result["ok"] = False
                        result["errors"].append("INVALID_RESOURCES: gpus must be an integer")
            
            # 检查评分器是否存在
            if "scorer" in meta:
                try:
                    # 避免 get_scorer 实例化副作用，改用 get_scorer_class 仅判断存在性
                    from autoscorer.scorers.registry import get_scorer_class
                    if get_scorer_class(meta["scorer"]) is None:
                        result["ok"] = False
                        result["errors"].append(f"SCORER_NOT_FOUND: {meta['scorer']}")
                except Exception as e:
                    result["ok"] = False
                    result["errors"].append(f"SCORER_ERROR: {e}")
                    
    except json.JSONDecodeError as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: meta.json invalid JSON: {e}")
    except UnicodeDecodeError as e:
        result["ok"] = False
        result["errors"].append(f"BAD_FORMAT: meta.json encoding error: {e}")
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: meta.json error: {e}")
    
    return result


def _validate_memory_format(memory_str: str) -> bool:
    """验证内存格式是否合法 (例如: 1Gi, 512Mi, 2g, 1024m)"""
    import re
    pattern = r'^\d+(\.\d+)?[gGmM]i?$'
    return bool(re.match(pattern, memory_str.strip()))


def validate_data_format(workspace: Path, task_type: str) -> dict:
    """[DEPRECATED] 统一数据校验已废弃，交由各评分器自行校验。

    现阶段仅进行最基本的存在性检查，避免重复实现和维护压力。
    """
    result = {"ok": True, "errors": []}
    ws = Path(workspace)
    # 基础存在性（如果 input 与 output 目录存在，视作通过；细节交由评分器处理）
    if not (ws / "input").exists():
        result["ok"] = False
        result["errors"].append("MISSING_FILE: input/")
    if not (ws / "output").exists():
        # output 可在运行时创建，但这里保持一致性提示
        (ws / "output").mkdir(parents=True, exist_ok=True)
    return result


def _validate_csv_id_only(path: Path, filename: str) -> dict:
    """验证CSV文件至少包含 id 列，适用于文本任务。

    - 检查文件存在与可解析
    - 检查是否包含 id 列
    - 检查是否有重复 id
    - 检查至少一行数据
    """
    result = {"ok": True, "errors": []}
    if not path.exists():
        result["ok"] = False
        result["errors"].append(f"MISSING_FILE: {filename}")
        return result
    try:
        import csv
        with path.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} has no header")
                return result
            if "id" not in reader.fieldnames:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} must contain id column")
                return result
            ids = set()
            row_count = 0
            for row in reader:
                row_count += 1
                if row["id"] in ids:
                    result["ok"] = False
                    result["errors"].append(f"MISMATCH: Duplicate ID in {filename}: {row['id']}")
                    break
                ids.add(row["id"])
            if row_count == 0:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} contains no data rows")
    except UnicodeDecodeError:
        result["ok"] = False
        result["errors"].append(f"BAD_FORMAT: {filename} encoding error, must be UTF-8")
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: {filename} parsing failed: {e}")
    return result


def _validate_csv_format(path: Path, filename: str) -> dict:
    """验证CSV文件格式"""
    result = {"ok": True, "errors": []}
    
    if not path.exists():
        result["ok"] = False
        result["errors"].append(f"MISSING_FILE: {filename}")
        return result
    
    try:
        import csv
        with path.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} has no header")
                return result
            
            if "id" not in reader.fieldnames or "label" not in reader.fieldnames:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} must contain id,label columns")
                return result
            
            # 检查是否有重复ID
            ids = set()
            row_count = 0
            for row in reader:
                row_count += 1
                if row["id"] in ids:
                    result["ok"] = False
                    result["errors"].append(f"MISMATCH: Duplicate ID in {filename}: {row['id']}")
                    break
                ids.add(row["id"])
            
            if row_count == 0:
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} contains no data rows")
                
    except UnicodeDecodeError:
        result["ok"] = False
        result["errors"].append(f"BAD_FORMAT: {filename} encoding error, must be UTF-8")
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: {filename} parsing failed: {e}")
    
    return result


def _validate_json_format(path: Path, filename: str) -> dict:
    """验证JSON文件格式"""
    result = {"ok": True, "errors": []}
    
    if not path.exists():
        result["ok"] = False
        result["errors"].append(f"MISSING_FILE: {filename}")
        return result
    
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        
        # 简单检查是否是列表格式
        if not isinstance(data, list):
            result["ok"] = False
            result["errors"].append(f"BAD_FORMAT: {filename} must be a JSON array")
            return result
        
        # 检查必需字段
        required_fields = ["image_id", "bbox", "category_id"]
        for i, item in enumerate(data[:5]):  # 只检查前5个
            if not isinstance(item, dict):
                result["ok"] = False
                result["errors"].append(f"BAD_FORMAT: {filename} item {i} must be an object")
                break
            
            for field in required_fields:
                if field not in item:
                    result["ok"] = False
                    result["errors"].append(f"BAD_FORMAT: {filename} item {i} missing field: {field}")
                    break
                    
    except json.JSONDecodeError as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: {filename} invalid JSON: {e}")
    except UnicodeDecodeError:
        result["ok"] = False
        result["errors"].append(f"BAD_FORMAT: {filename} encoding error, must be UTF-8")
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"PARSE_ERROR: {filename} error: {e}")
    
    return result


def _get_csv_ids(path: Path) -> set:
    """获取CSV文件中的所有ID"""
    import csv
    ids = set()
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row["id"])
    return ids


def _validate_regression_labels(path: Path) -> None:
    """验证回归任务的label是否都是数值"""
    import csv
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                float(row["label"])
            except (ValueError, TypeError):
                raise ValueError(f"label in row {i+1} cannot be converted to float: {row['label']}")
