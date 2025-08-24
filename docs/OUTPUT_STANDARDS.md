# 输出标准化规范 v2.0

## 1. 概述

本文档定义了AutoScorer系统中所有输出的标准化格式，确保跨平台、多场景的一致性和互操作性。

### 1.1 标准化目标

- **统一格式**: 所有输出采用一致的JSON结构
- **向后兼容**: 版本升级保持接口兼容性
- **类型安全**: 明确的数据类型和约束定义
- **可扩展性**: 支持自定义字段和算法特定输出
- **国际化**: 支持多语言错误消息和描述

### 1.2 适用范围

本标准适用于：

- 评分结果输出 (Result Schema)
- API响应格式 (REST API)
- CLI命令输出 (Command Line)
- 错误信息格式 (Error Handling)
- 日志记录格式 (Logging)


## 2. 核心评分结果标准 (Result Schema)

### 2.1 基础结构定义

```json
{
  "summary": {
    "score": 0.85,
    "rank": "A",
    "pass": true,
    "primary_metric": "f1_macro"
  },
  "metrics": {
    "f1_macro": 0.85,
    "accuracy": 0.92,
    "precision_macro": 0.83,
    "recall_macro": 0.87,
    "num_samples": 1000,
    "num_classes": 5
  },
  "artifacts": {
    "confusion_matrix": {
      "path": "output/confusion_matrix.png",
      "size": 15420,
      "sha256": "d4e1f2a3b5c6...",
      "content_type": "image/png",
      "metadata": {
        "classes": ["cat", "dog", "bird"],
        "format": "normalized"
      }
    },
    "classification_report": {
      "path": "output/classification_report.json",
      "size": 2048,
      "sha256": "a1b2c3d4e5f6...",
      "content_type": "application/json"
    }
  },
  "timing": {
    "total_time": 1.234,
    "load_time": 0.156,
    "compute_time": 0.987,
    "save_time": 0.091,
    "breakdown": {
      "data_validation": 0.045,
      "metric_calculation": 0.832,
      "result_generation": 0.110
    }
  },
  "resources": {
    "memory_peak_mb": 512.3,
    "memory_average_mb": 256.7,
    "cpu_usage_percent": 45.2,
    "disk_usage_mb": 1024.0,
    "gpu_memory_mb": 2048.0
  },
  "versioning": {
    "scorer": "classification_f1",
    "version": "2.0.0",
    "algorithm": "Macro-F1 with per-class precision and recall",
    "timestamp": "2024-08-21T10:30:00.123Z",
    "commit_hash": "a1b2c3d4",
    "environment": {
      "python_version": "3.10.12",
      "numpy_version": "1.24.3",
      "sklearn_version": "1.3.0"
    }
  },
  "validation": {
    "data_format_valid": true,
    "id_consistency_valid": true,
    "value_range_valid": true,
    "completeness_score": 1.0,
    "warnings": [],
    "errors": []
  },
  "error": null
}
```

### 2.2 字段详细规范

#### 2.2.1 summary 字段 (必需)

**用途**: 提供评分核心摘要，便于快速理解结果

| 字段名 | 类型 | 必需 | 说明 | 示例 | 约束 |
|--------|------|------|------|------|------|
| `score` | number | ✅ | 主要评分值 | 0.85 | [0.0, 1.0] 或算法特定范围 |
| `rank` | string | ❌ | 等级评定 | "A" | A/B/C/D 或 优/良/中/差 |
| `pass` | boolean | ❌ | 是否通过阈值 | true | true/false |
| `primary_metric` | string | ✅ | 主要指标名称 | "f1_macro" | 必须在metrics中存在 |

**算法特定标准字段**:

| 算法类型 | 主要字段 | 取值范围 | 备注 |
|---------|---------|---------|------|
| 分类 | `f1_macro`, `accuracy` | [0.0, 1.0] | 优先使用f1_macro |
| 回归 | `rmse`, `mae` | [0.0, +∞) | 值越小越好 |
| 检测 | `map`, `map_50` | [0.0, 1.0] | mAP@0.5或多阈值 |
| 排序 | `ndcg`, `map` | [0.0, 1.0] | 信息检索指标 |

#### 2.2.2 metrics 字段 (必需)

**用途**: 详细的评价指标数据

**格式要求**:

- 所有数值必须为 `number` 类型 (float/int)
- 键名使用 `snake_case` 格式
- 必须包含 `summary.primary_metric` 中指定的指标
- 可包含算法特定的扩展指标

**分类任务标准指标**:

```json
{
  "f1_macro": 0.85,
  "f1_micro": 0.88,
  "f1_weighted": 0.86,
  "accuracy": 0.92,
  "precision_macro": 0.83,
  "recall_macro": 0.87,
  "num_samples": 1000,
  "num_classes": 5,
  "per_class_f1": {
    "class_a": 0.89,
    "class_b": 0.82,
    "class_c": 0.84
  }
}
```

**回归任务标准指标**:

```json
{
  "rmse": 0.234,
  "mae": 0.189,
  "mse": 0.055,
  "r_squared": 0.891,
  "mean_absolute_percentage_error": 8.7,
  "num_samples": 500,
  "gt_mean": 12.45,
  "pred_mean": 12.38
}
```

#### 2.2.3 artifacts 字段 (可选)

**用途**: 生成的文件和资源信息

**标准结构**:

```json
{
  "artifact_name": {
    "path": "相对于workspace的路径",
    "size": "文件大小(字节)",
    "sha256": "文件SHA256哈希",
    "content_type": "MIME类型",
    "metadata": "自定义元数据对象"
  }
}
```

**常见artifact类型**:

| 类型 | content_type | 说明 | 示例路径 |
|------|-------------|------|----------|
| 混淆矩阵 | image/png | 可视化混淆矩阵 | output/confusion_matrix.png |
| 分类报告 | application/json | 详细分类报告 | output/classification_report.json |
| 回归图表 | image/svg+xml | 预测vs真实值散点图 | output/regression_plot.svg |
| 检测可视化 | image/jpeg | 标注检测结果的图像 | output/detection_results.jpg |
| 原始数据 | text/csv | 详细预测结果 | output/detailed_predictions.csv |

#### 2.2.4 timing 字段 (推荐)

**用途**: 性能时间分析

```json
{
  "total_time": 1.234,
  "load_time": 0.156,
  "compute_time": 0.987,
  "save_time": 0.091,
  "breakdown": {
    "data_validation": 0.045,
    "metric_calculation": 0.832,
    "visualization_generation": 0.110
  }
}
```

#### 2.2.5 resources 字段 (推荐)

**用途**: 资源使用统计

```json
{
  "memory_peak_mb": 512.3,
  "memory_average_mb": 256.7,
  "cpu_usage_percent": 45.2,
  "disk_usage_mb": 1024.0,
  "gpu_memory_mb": 2048.0,
  "network_io_mb": 15.3
}
```

#### 2.2.6 versioning 字段 (必需)

**用途**: 版本和可追溯性信息

| 字段名 | 类型 | 必需 | 说明 | 示例 |
|--------|------|------|------|------|
| `scorer` | string | ✅ | 评分器名称 | "classification_f1" |
| `version` | string | ✅ | 评分器版本 | "2.0.0" |
| `algorithm` | string | ❌ | 算法描述 | "Macro-F1 with..." |
| `timestamp` | string | ✅ | ISO格式时间戳 | "2024-08-21T10:30:00.123Z" |
| `commit_hash` | string | ❌ | 代码提交哈希 | "a1b2c3d4" |
| `environment` | object | ❌ | 运行环境信息 | 见示例 |

#### 2.2.7 validation 字段 (推荐)

**用途**: 数据验证结果

```json
{
  "data_format_valid": true,
  "id_consistency_valid": true,
  "value_range_valid": true,
  "completeness_score": 1.0,
  "warnings": [
    {
      "code": "MINOR_INCONSISTENCY",
      "message": "Some predicted probabilities sum to slightly more than 1.0",
      "count": 3
    }
  ],
  "errors": []
}
```

#### 2.2.8 error 字段 (条件必需)

**用途**: 错误信息，仅在出错时存在

```json
{
  "code": "DATA_MISMATCH_ERROR",
  "message": "Prediction IDs do not match ground truth IDs",
  "stage": "validation",
  "details": {
    "missing_ids": ["sample_005", "sample_012"],
    "extra_ids": ["sample_999"],
    "total_mismatches": 3
  }
}
```

## 3. 算法特定输出标准

### 3.1 分类算法输出

#### 3.1.1 二分类输出示例

```json
{
  "summary": {
    "score": 0.89,
    "rank": "A",
    "pass": true,
    "primary_metric": "f1_score"
  },
  "metrics": {
    "f1_score": 0.89,
    "precision": 0.92,
    "recall": 0.86,
    "accuracy": 0.91,
    "specificity": 0.94,
    "auc_roc": 0.95,
    "auc_pr": 0.91,
    "true_positives": 86,
    "true_negatives": 189,
    "false_positives": 12,
    "false_negatives": 13,
    "num_samples": 300,
    "positive_rate": 0.33
  }
}
```

#### 3.1.2 多分类输出示例

```json
{
  "summary": {
    "score": 0.85,
    "rank": "A", 
    "pass": true,
    "primary_metric": "f1_macro"
  },
  "metrics": {
    "f1_macro": 0.85,
    "f1_micro": 0.88,
    "f1_weighted": 0.86,
    "accuracy": 0.88,
    "precision_macro": 0.83,
    "recall_macro": 0.87,
    "num_samples": 1000,
    "num_classes": 5,
    "per_class_metrics": {
      "cat": {"f1": 0.89, "precision": 0.91, "recall": 0.87, "support": 200},
      "dog": {"f1": 0.82, "precision": 0.78, "recall": 0.86, "support": 180},
      "bird": {"f1": 0.84, "precision": 0.88, "recall": 0.80, "support": 220},
      "fish": {"f1": 0.87, "precision": 0.85, "recall": 0.89, "support": 190},
      "rabbit": {"f1": 0.83, "precision": 0.81, "recall": 0.85, "support": 210}
    }
  },
  "artifacts": {
    "confusion_matrix": {
      "path": "output/confusion_matrix.png",
      "size": 25600,
      "content_type": "image/png",
      "metadata": {
        "classes": ["cat", "dog", "bird", "fish", "rabbit"],
        "normalized": true
      }
    }
  }
}
```

### 3.2 回归算法输出

```json
{
  "summary": {
    "score": 0.234,
    "rank": "B",
    "pass": true,
    "primary_metric": "rmse"
  },
  "metrics": {
    "rmse": 0.234,
    "mae": 0.189,
    "mse": 0.055,
    "r_squared": 0.891,
    "mean_absolute_percentage_error": 8.7,
    "max_error": 0.892,
    "num_samples": 500,
    "gt_mean": 12.45,
    "gt_std": 3.21,
    "pred_mean": 12.38,
    "pred_std": 3.15,
    "correlation_coefficient": 0.944
  },
  "artifacts": {
    "scatter_plot": {
      "path": "output/prediction_vs_ground_truth.png",
      "size": 18432,
      "content_type": "image/png"
    },
    "residual_plot": {
      "path": "output/residual_analysis.png", 
      "size": 16384,
      "content_type": "image/png"
    }
  }
}
```

### 3.3 检测算法输出

```json
{
  "summary": {
    "score": 0.675,
    "rank": "B",
    "pass": true,
    "primary_metric": "map_50"
  },
  "metrics": {
    "map_50": 0.675,
    "map_75": 0.542,
    "map_50_95": 0.489,
    "precision_50": 0.782,
    "recall_50": 0.698,
    "num_images": 500,
    "num_annotations": 1247,
    "num_predictions": 1156,
    "per_class_ap": {
      "person": {"ap_50": 0.72, "ap_75": 0.65, "num_gt": 420},
      "car": {"ap_50": 0.68, "ap_75": 0.48, "num_gt": 380},
      "bicycle": {"ap_50": 0.62, "ap_75": 0.45, "num_gt": 447}
    },
    "per_size_ap": {
      "small": 0.45,
      "medium": 0.67,
      "large": 0.82
    }
  },
  "artifacts": {
    "detection_visualization": {
      "path": "output/detection_samples.jpg",
      "size": 345600,
      "content_type": "image/jpeg",
      "metadata": {
        "num_samples": 20,
        "confidence_threshold": 0.5
      }
    }
  }
}
```

<!-- 统一API输出规范章节已在文档后半部分“3. API输出标准化”中详述，这里移除重复内容以避免歧义。 -->

## 2. 评分结果标准化要求

### 2.1 Summary字段统一规范

为确保不同算法输出的一致性，summary字段必须遵循以下规则：

1. **主评分字段**: 每种算法类型必须有标准的主评分字段名
2. **数值范围**: 明确定义每个指标的取值范围
3. **缺失处理**: 明确如何处理无法计算的指标

#### 算法类型对应的主评分字段

| 算法类型 | 主评分字段 | 取值范围 | 说明 |
|---------|-----------|---------|------|
| 分类 | `accuracy` 或 `f1_macro` | [0.0, 1.0] | 准确率或宏平均F1 |
| 回归 | `rmse` | [0.0, +∞) | 均方根误差，越小越好 |
| 检测 | `map` 或 `map50` | [0.0, 1.0] | 平均精度 |
| 排序 | `ndcg` 或 `map` | [0.0, 1.0] | 归一化折损累计增益 |
| 聚类 | `silhouette` | [-1.0, 1.0] | 轮廓系数 |

### 2.2 评分器实现标准

每个评分器必须:

1. 返回符合Result schema的结果
2. 在summary中包含算法主要指标
3. 提供versioning信息
4. 正确处理异常并返回标准化错误

## 3. API输出标准化

### 3.1 成功响应格式

所有API成功响应使用以下格式:

```json
{
  "ok": true,
  "data": {
    // 具体数据内容
  },
  "meta": {
    "timestamp": "2025-08-21T10:30:00Z",
    "request_id": "req_123456",
    "version": "0.1.0"
  }
}
```

### 3.2 错误响应格式

API错误响应使用标准化格式:

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "stage": "pipeline_stage",
    "details": {
      "additional": "information"
    }
  },
  "meta": {
    "timestamp": "2025-08-21T10:30:00Z",
    "request_id": "req_123456",
    "version": "0.1.0"
  }
}
```

### 3.3 主要API端点输出标准

#### 3.3.1 `/score` - 评分接口

**成功响应**:

```json
{
  "ok": true,
  "data": {
    // Result schema 完整内容
  },
  "meta": {
    "scorer_used": "classification_f1",
    "execution_time": 1.23,
    "timestamp": "2025-08-21T10:30:00Z"
  }
}
```

#### 3.3.2 `/pipeline` - 流水线接口

**成功响应**:

```json
{
  "ok": true,
  "data": {
    "run_result": {
      "status": "success",
      "execution_time": 5.67,
      "output_files": ["pred.csv"]
    },
    "score_result": {
      // Result schema 完整内容
    }
  },
  "meta": {
    "backend_used": "docker",
    "scorer_used": "classification_f1",
    "total_time": 6.90,
    "timestamp": "2025-08-21T10:30:00Z"
  }
}
```

#### 3.3.3 `/scorers` - 评分器管理

**列表响应**:

```json
{
  "ok": true,
  "data": {
    "scorers": {
      "scorer_name": "ScorerClassName"
    },
    "total": 5,
    "watched_files": ["/path/to/file.py"]
  },
  "meta": {
    "timestamp": "2025-08-21T10:30:00Z"
  }
}
```

## 4. CLI输出标准化

### 4.1 成功输出格式

CLI命令成功时输出JSON格式:

```json
{
  "status": "success",
  "data": {
    // 命令特定数据
  },
  "execution_time": 1.23,
  "timestamp": "2025-08-21T10:30:00Z"
}
```

### 4.2 错误输出格式

CLI命令出错时输出:

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE", 
    "message": "Error description",
    "stage": "execution_stage"
  },
  "timestamp": "2025-08-21T10:30:00Z"
}
```

### 4.3 具体命令输出标准

#### 4.3.1 评分命令 (`score`)

```json
{
  "status": "success",
  "data": {
    // Result schema 完整内容
  },
  "execution_time": 1.23,
  "workspace": "/path/to/workspace",
  "scorer_used": "classification_f1",
  "timestamp": "2025-08-21T10:30:00Z"
}
```

#### 4.3.2 流水线命令 (`pipeline`)

```json
{
  "status": "success",
  "data": {
    "run_phase": {
      "status": "success",
      "time": 5.67
    },
    "score_phase": {
      // Result schema 完整内容
    }
  },
  "execution_time": 6.90,
  "workspace": "/path/to/workspace",
  "backend_used": "docker",
  "scorer_used": "classification_f1",
  "timestamp": "2025-08-21T10:30:00Z"
}
```

#### 4.3.3 评分器管理命令 (`scorers`)

```json
{
  "status": "success",
  "action": "list|load|reload|test",
  "data": {
    // 操作特定数据
  },
  "timestamp": "2025-08-21T10:30:00Z"
}
```

## 5. 错误标准化

### 5.1 错误代码分类

错误代码采用分级命名:

- `INPUT_*`: 输入相关错误
- `VALIDATION_*`: 校验相关错误  
- `EXECUTION_*`: 执行相关错误
- `SCORE_*`: 评分相关错误
- `SYSTEM_*`: 系统相关错误

### 5.2 标准错误格式

```json
{
  "code": "ERROR_CATEGORY_SPECIFIC",
  "message": "Human readable description",
  "stage": "pipeline_stage",
  "details": {
    "file": "problematic_file.py",
    "line": 42,
    "context": "additional_context"
  }
}
```

### 5.3 常见错误代码

| 错误代码 | 描述 | 阶段 |
|---------|------|------|
| `INPUT_FILE_NOT_FOUND` | 输入文件未找到 | validation |
| `INPUT_FORMAT_INVALID` | 输入格式不正确 | validation |
| `VALIDATION_DATA_MISMATCH` | 数据不匹配 | validation |
| `EXECUTION_DOCKER_FAILED` | Docker执行失败 | execution |
| `EXECUTION_TIMEOUT` | 执行超时 | execution |
| `SCORE_ALGORITHM_ERROR` | 评分算法错误 | scoring |
| `SCORE_METRICS_INVALID` | 指标计算无效 | scoring |
| `SYSTEM_RESOURCE_LIMIT` | 系统资源不足 | system |
| `SYSTEM_PERMISSION_DENIED` | 权限不足 | system |

## 6. 实施检查清单

### 6.1 评分器检查

- [ ] summary字段包含主评分指标
- [ ] 指标名称符合算法类型标准
- [ ] versioning信息完整
- [ ] 错误处理返回标准格式
- [ ] 数值类型正确(float)

### 6.2 API接口检查

- [ ] 所有响应包含ok字段
- [ ] 错误响应格式统一
- [ ] meta信息完整
- [ ] 时间戳格式统一(ISO)

### 6.3 CLI输出检查

- [ ] JSON格式输出
- [ ] status字段明确
- [ ] 错误信息标准化
- [ ] 执行时间记录

### 6.4 文档同步检查

- [ ] API文档与实际输出一致
- [ ] 错误代码文档完整
- [ ] 示例输出准确
- [ ] 版本信息同步

## 7. 向后兼容性

### 7.1 字段扩展原则

- 新增字段只能是可选的
- 不能修改现有字段的数据类型
- 不能删除现有的必需字段
- 字段重命名需要保持别名支持

### 7.2 版本管理

- API版本通过header或路径控制
- Result schema版本通过versioning字段追踪
- 向后兼容性至少保持3个主版本

## 8. 监控和质量控制

### 8.1 输出格式验证

- 自动化测试验证所有输出格式
- Schema validation集成到CI/CD
- 定期审计输出一致性

### 8.2 性能监控

- 记录输出生成时间
- 监控输出大小
- 追踪format compliance率

### 8.3 质量指标

- Format compliance: >99%
- Response time: <100ms (API)
- Error rate: <1%
- Schema evolution compatibility: 100%
