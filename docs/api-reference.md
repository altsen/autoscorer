# API 参考手册

本文档提供 AutoScorer REST API 的完整参考，包括所有端点、请求/响应格式、错误处理和使用示例。

## API 概述

AutoScorer API 是基于 REST 的 HTTP API，使用 JSON 进行数据交换。API 遵循 RESTful 设计原则，提供统一的接口用于任务提交、状态查询、评分器管理等功能。

### 基础信息

- **Base URL**: `http://localhost:8000`
- **API Version**: `v1`
- **Content-Type**: `application/json`
- **Authentication**: API Key (可选)

### API 特性

- **统一响应格式**: 所有响应都使用标准化的格式
- **错误处理**: 详细的错误码和消息
- **版本控制**: 支持 API 版本管理
- **异步支持**: 长时间运行的任务支持异步处理
- **批量操作**: 支持批量提交和查询

## 通用规范

### 请求格式

所有 API 请求都应该：

```http
POST /api/v1/jobs HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Authorization: Bearer <token>  # 可选
User-Agent: autoscorer-client/1.0.0

{
  "job_id": "unique-job-id",
  "task_type": "classification",
  "scorer": "classification_f1"
}
```

### 响应格式

所有 API 响应都使用统一的格式：

```json
{
  "success": true,
  "data": {
    // 具体数据内容
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "request_id": "req_abc123",
    "api_version": "v1"
  },
  "errors": []  // 仅在出错时存在
}
```

#### 成功响应

```json
{
  "success": true,
  "data": {
    "job_id": "job-001",
    "status": "completed",
    "result": {
      "summary": {
        "score": 0.85
      }
    }
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "request_id": "req_abc123",
    "api_version": "v1"
  }
}
```

#### 错误响应

```json
{
  "success": false,
  "data": null,
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "request_id": "req_abc123",
    "api_version": "v1"
  },
  "errors": [
    {
      "code": "INVALID_PARAMETER",
      "message": "Invalid scorer name",
      "field": "scorer",
      "details": {
        "provided": "invalid_scorer",
        "available": ["classification_f1", "regression_rmse"]
      }
    }
  ]
}
```

### HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| `200` | OK | 请求成功 |
| `201` | Created | 资源创建成功 |
| `202` | Accepted | 异步请求已接受 |
| `400` | Bad Request | 请求参数错误 |
| `401` | Unauthorized | 认证失败 |
| `403` | Forbidden | 权限不足 |
| `404` | Not Found | 资源不存在 |
| `409` | Conflict | 资源冲突 |
| `422` | Unprocessable Entity | 请求格式正确但逻辑错误 |
| `429` | Too Many Requests | 请求频率超限 |
| `500` | Internal Server Error | 服务器内部错误 |
| `503` | Service Unavailable | 服务不可用 |

## 系统信息 API

### 健康检查

检查系统是否正常运行。

```http
GET /health
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "2.0.0",
    "uptime": "2 days, 14:30:25",
    "components": {
      "redis": "healthy",
      "docker": "healthy",
      "k8s": "unavailable"
    }
  }
}
```

### 系统状态

获取详细的系统状态信息。

```http
GET /api/v1/status
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "system": {
      "version": "2.0.0",
      "uptime": "2 days, 14:30:25",
      "environment": "production"
    },
    "metrics": {
      "total_jobs": 1250,
      "active_jobs": 15,
      "completed_jobs": 1180,
      "failed_jobs": 55,
      "success_rate": 0.956
    },
    "resources": {
      "cpu_usage": 0.65,
      "memory_usage": 0.78,
      "disk_usage": 0.45
    },
    "executors": {
      "docker": {
        "status": "healthy",
        "active_containers": 8,
        "available_cores": 16,
        "available_memory": "32Gi"
      },
      "k8s": {
        "status": "unavailable",
        "reason": "cluster not configured"
      }
    }
  }
}
```

## 任务管理 API

### 提交任务

提交新的评分任务。

```http
POST /api/v1/jobs
```

**请求体:**

```json
{
  "job_id": "job-demo-001",
  "task_type": "classification",
  "scorer": "classification_f1",
  "workspace_path": "/path/to/workspace",
  "executor": "docker",  // 可选，自动选择
  "async": true,         // 可选，默认 false
  "config": {            // 可选，覆盖默认配置
    "time_limit": 1800,
    "resources": {
      "cpu": 2.0,
      "memory": "4Gi",
      "gpus": 0
    },
    "scorer_params": {
      "average": "macro"
    }
  }
}
```

**响应示例 (同步):**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "status": "completed",
    "execution_time": 45.6,
    "result": {
      "summary": {
        "score": 0.85,
        "rank": "A",
        "pass": true
      },
      "metrics": {
        "f1_macro": 0.85,
        "accuracy": 0.88,
        "precision": 0.83,
        "recall": 0.87
      },
      "timing": {
        "total_time": 45.6,
        "inference_time": 42.1,
        "scoring_time": 3.5
      },
      "versioning": {
        "scorer": "classification_f1",
        "version": "2.0.0",
        "timestamp": "2024-08-24T10:00:00Z"
      }
    }
  }
}
```

**响应示例 (异步):**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "status": "submitted",
    "message": "Job submitted for async processing",
    "estimated_completion": "2024-08-24T10:15:00Z"
  }
}
```

### 批量提交任务

批量提交多个任务。

```http
POST /api/v1/jobs/batch
```

**请求体:**

```json
{
  "jobs": [
    {
      "job_id": "job-001",
      "task_type": "classification",
      "scorer": "classification_f1",
      "workspace_path": "/path/to/workspace1"
    },
    {
      "job_id": "job-002", 
      "task_type": "regression",
      "scorer": "regression_rmse",
      "workspace_path": "/path/to/workspace2"
    }
  ],
  "async": true,
  "max_parallel": 5  // 可选，最大并行数
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "batch_id": "batch-001",
    "submitted_jobs": 2,
    "status": "processing",
    "jobs": [
      {
        "job_id": "job-001",
        "status": "submitted"
      },
      {
        "job_id": "job-002",
        "status": "submitted"
      }
    ]
  }
}
```

### 查询任务状态

查询特定任务的状态信息。

```http
GET /api/v1/jobs/{job_id}/status
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "status": "running",
    "progress": 0.75,
    "created_at": "2024-08-24T10:00:00Z",
    "started_at": "2024-08-24T10:00:30Z",
    "estimated_completion": "2024-08-24T10:15:00Z",
    "executor": "docker",
    "resources": {
      "cpu_usage": 1.8,
      "memory_usage": "3.2Gi",
      "gpu_usage": 0
    },
    "logs_available": true
  }
}
```

### 获取任务结果

获取已完成任务的详细结果。

```http
GET /api/v1/jobs/{job_id}/result
```

**查询参数:**
- `include_artifacts`: 是否包含产物文件信息 (boolean)
- `include_logs`: 是否包含日志信息 (boolean)

**响应示例:**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "status": "completed",
    "result": {
      "summary": {
        "score": 0.85,
        "rank": "A",
        "pass": true,
        "message": "Evaluation completed successfully"
      },
      "metrics": {
        "f1_macro": 0.85,
        "f1_micro": 0.88,
        "precision_macro": 0.83,
        "recall_macro": 0.87,
        "accuracy": 0.88,
        "confusion_matrix": [[45, 5], [8, 42]]
      },
      "artifacts": {
        "confusion_matrix": {
          "path": "/workspace/output/artifacts/confusion_matrix.png",
          "size": 1024,
          "type": "image/png"
        }
      },
      "timing": {
        "total_time": 45.6,
        "data_loading": 1.2,
        "inference_time": 42.1,
        "scoring_time": 3.5
      },
      "resources": {
        "peak_cpu": 1.95,
        "peak_memory": "3.8Gi",
        "total_disk_io": "50MB"
      },
      "versioning": {
        "scorer": "classification_f1",
        "version": "2.0.0",
        "autoscorer_version": "2.0.0",
        "timestamp": "2024-08-24T10:00:00Z"
      }
    },
    "logs": [
      {
        "timestamp": "2024-08-24T10:00:30Z",
        "level": "INFO",
        "message": "Starting evaluation process"
      },
      {
        "timestamp": "2024-08-24T10:01:15Z", 
        "level": "INFO",
        "message": "Evaluation completed successfully"
      }
    ]
  }
}
```

### 获取任务日志

获取任务执行日志。

```http
GET /api/v1/jobs/{job_id}/logs
```

**查询参数:**
- `level`: 日志级别过滤 (debug|info|warning|error)
- `since`: 开始时间 (ISO 8601 格式)
- `tail`: 返回最后 N 行 (integer)
- `follow`: 是否流式输出 (boolean)

**响应示例:**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "logs": [
      {
        "timestamp": "2024-08-24T10:00:30Z",
        "level": "INFO",
        "component": "executor",
        "message": "Starting container execution"
      },
      {
        "timestamp": "2024-08-24T10:00:45Z",
        "level": "DEBUG",
        "component": "scorer",
        "message": "Loading ground truth data: 1000 samples"
      },
      {
        "timestamp": "2024-08-24T10:01:10Z",
        "level": "INFO",
        "component": "scorer", 
        "message": "F1 score calculation completed: 0.85"
      }
    ],
    "total_lines": 156,
    "has_more": true
  }
}
```

### 取消任务

取消正在运行或排队的任务。

```http
DELETE /api/v1/jobs/{job_id}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "job_id": "job-demo-001",
    "status": "cancelled",
    "cancelled_at": "2024-08-24T10:05:00Z",
    "reason": "User requested cancellation"
  }
}
```

### 列出所有任务

获取任务列表。

```http
GET /api/v1/jobs
```

**查询参数:**
- `status`: 状态过滤 (submitted|running|completed|failed|cancelled)
- `task_type`: 任务类型过滤 (classification|regression|detection)
- `scorer`: 评分器过滤
- `limit`: 返回数量限制 (默认 50)
- `offset`: 偏移量 (默认 0)
- `sort`: 排序字段 (created_at|updated_at|job_id)
- `order`: 排序方向 (asc|desc)

**响应示例:**

```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "job_id": "job-demo-001",
        "status": "completed",
        "task_type": "classification",
        "scorer": "classification_f1",
        "created_at": "2024-08-24T10:00:00Z",
        "completed_at": "2024-08-24T10:01:15Z",
        "execution_time": 45.6,
        "score": 0.85
      },
      {
        "job_id": "job-demo-002",
        "status": "running",
        "task_type": "regression",
        "scorer": "regression_rmse",
        "created_at": "2024-08-24T10:02:00Z",
        "started_at": "2024-08-24T10:02:30Z",
        "progress": 0.45
      }
    ],
    "pagination": {
      "total": 1250,
      "limit": 50,
      "offset": 0,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

## 评分器管理 API

### 列出所有评分器

获取系统中可用的评分器列表。

```http
GET /api/v1/scorers
```

**查询参数:**
- `task_type`: 按任务类型过滤
- `format`: 返回格式 (json|table)
- `include_details`: 是否包含详细信息

**响应示例:**

```json
{
  "success": true,
  "data": [
    {
      "name": "classification_f1",
      "version": "2.0.0",
      "description": "F1-score for classification tasks",
      "task_type": "classification",
      "supported_formats": ["csv"],
      "parameters": {
        "average": {
          "type": "string",
          "default": "macro",
          "choices": ["macro", "micro", "weighted"],
          "description": "Averaging strategy for F1 calculation"
        },
        "labels": {
          "type": "array",
          "default": null,
          "description": "List of labels to include in calculation"
        }
      },
      "created_at": "2024-08-24T09:00:00Z",
      "last_used": "2024-08-24T10:00:00Z",
      "usage_count": 1205
    },
    {
      "name": "regression_rmse",
      "version": "2.0.0", 
      "description": "Root Mean Square Error for regression tasks",
      "task_type": "regression",
      "supported_formats": ["csv"],
      "parameters": {
        "sample_weight": {
          "type": "array",
          "default": null,
          "description": "Sample weights for weighted RMSE"
        }
      },
      "created_at": "2024-08-24T09:00:00Z",
      "last_used": "2024-08-24T09:45:00Z",
      "usage_count": 856
    }
  ]
}
```

### 获取评分器详情

获取特定评分器的详细信息。

```http
GET /api/v1/scorers/{scorer_name}
```

**查询参数:**
- `version`: 指定版本号
- `include_examples`: 是否包含使用示例

**响应示例:**

```json
{
  "success": true,
  "data": {
    "name": "classification_f1",
    "version": "2.0.0",
    "description": "F1-score calculation for multi-class classification tasks with support for different averaging strategies",
    "task_type": "classification",
    "supported_formats": ["csv"],
    "author": "AutoScorer Team",
    "documentation": "https://docs.autoscorer.com/scorers/classification_f1",
    "parameters": {
      "average": {
        "type": "string",
        "default": "macro",
        "choices": ["macro", "micro", "weighted"],
        "description": "Averaging strategy for F1 calculation",
        "required": false
      },
      "labels": {
        "type": "array",
        "default": null,
        "description": "List of labels to include in calculation. If None, all labels are used",
        "required": false
      },
      "sample_weight": {
        "type": "array", 
        "default": null,
        "description": "Sample weights for weighted calculations",
        "required": false
      }
    },
    "input_format": {
      "gt_file": "input/gt.csv",
      "pred_file": "output/pred.csv",
      "required_columns": ["id", "label"],
      "data_types": {
        "id": "string|integer",
        "label": "string|integer"
      }
    },
    "output_format": {
      "primary_metric": "f1_macro",
      "additional_metrics": [
        "f1_micro", "f1_weighted", 
        "precision_macro", "recall_macro", 
        "accuracy"
      ]
    },
    "examples": [
      {
        "name": "Basic usage",
        "description": "Standard F1 calculation with macro averaging",
        "parameters": {
          "average": "macro"
        },
        "expected_output": {
          "f1_macro": 0.85,
          "accuracy": 0.88
        }
      }
    ],
    "created_at": "2024-08-24T09:00:00Z",
    "updated_at": "2024-08-24T09:00:00Z",
    "last_used": "2024-08-24T10:00:00Z",
    "usage_count": 1205,
    "success_rate": 0.995
  }
}
```

### 测试评分器

测试评分器在指定工作区上的运行效果。

```http
POST /api/v1/scorers/{scorer_name}/test
```

**请求体:**

```json
{
  "workspace_path": "/path/to/test/workspace",
  "parameters": {
    "average": "macro",
    "labels": ["A", "B", "C"]
  },
  "validate_only": false  // 仅验证不执行
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "scorer": "classification_f1",
    "test_status": "passed",
    "execution_time": 0.45,
    "result": {
      "summary": {
        "score": 0.85,
        "rank": "A",
        "pass": true
      },
      "metrics": {
        "f1_macro": 0.85,
        "accuracy": 0.88
      }
    },
    "validation": {
      "workspace_valid": true,
      "data_format_valid": true,
      "parameters_valid": true
    },
    "performance": {
      "memory_usage": "45MB",
      "cpu_time": 0.42
    }
  }
}
```

### 加载自定义评分器

从文件加载自定义评分器。

```http
POST /api/v1/scorers/load
```

**请求体:**

```json
{
  "file_path": "/path/to/custom_scorer.py",
  "auto_watch": true,      // 自动监控文件变化
  "check_interval": 1.0,   // 监控间隔(秒)
  "force_reload": false    // 强制重新加载
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "loaded_scorers": [
      {
        "name": "custom_nlp_scorer",
        "version": "1.0.0",
        "file_path": "/path/to/custom_scorer.py",
        "loaded_at": "2024-08-24T10:00:00Z"
      }
    ],
    "watch_enabled": true,
    "total_loaded": 1
  }
}
```

### 重新加载评分器

重新加载指定的评分器文件。

```http
POST /api/v1/scorers/reload
```

**请求体:**

```json
{
  "file_path": "/path/to/custom_scorer.py",
  "scorer_name": "custom_nlp_scorer"  // 可选，指定评分器名称
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "reloaded_scorers": [
      {
        "name": "custom_nlp_scorer",
        "old_version": "1.0.0",
        "new_version": "1.1.0",
        "reloaded_at": "2024-08-24T10:05:00Z"
      }
    ],
    "total_reloaded": 1
  }
}
```

### 监控评分器文件

开始监控评分器文件的变化。

```http
POST /api/v1/scorers/watch
```

**请求体:**

```json
{
  "file_path": "/path/to/custom_scorer.py",
  "check_interval": 1.0  // 检查间隔(秒)
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "file_path": "/path/to/custom_scorer.py",
    "watch_started": true,
    "check_interval": 1.0,
    "started_at": "2024-08-24T10:00:00Z"
  }
}
```

### 停止监控评分器文件

停止监控特定文件。

```http
DELETE /api/v1/scorers/watch
```

**查询参数:**
- `file_path`: 要停止监控的文件路径

**响应示例:**

```json
{
  "success": true,
  "data": {
    "file_path": "/path/to/custom_scorer.py",
    "watch_stopped": true,
    "stopped_at": "2024-08-24T10:10:00Z"
  }
}
```

### 查看监控状态

查看当前的文件监控状态。

```http
GET /api/v1/scorers/watch
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "watched_files": [
      {
        "file_path": "/path/to/custom_scorer.py",
        "check_interval": 1.0,
        "started_at": "2024-08-24T10:00:00Z",
        "last_check": "2024-08-24T10:10:30Z",
        "total_reloads": 2
      }
    ],
    "total_watched": 1
  }
}
```

## 工作区管理 API

### 验证工作区

验证工作区结构和数据格式。

```http
POST /api/v1/workspaces/validate
```

**请求体:**

```json
{
  "workspace_path": "/path/to/workspace",
  "task_type": "classification",  // 可选
  "scorer": "classification_f1",  // 可选
  "strict_mode": true,            // 严格模式
  "auto_fix": false              // 自动修复
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "workspace_path": "/path/to/workspace",
    "validation_status": "valid",
    "checks": {
      "structure": {
        "status": "valid",
        "details": {
          "has_input_dir": true,
          "has_output_dir": true,
          "has_meta_json": true
        }
      },
      "data_format": {
        "status": "valid",
        "details": {
          "gt_file_exists": true,
          "gt_format_valid": true,
          "pred_file_exists": true,
          "pred_format_valid": true
        }
      },
      "configuration": {
        "status": "valid",
        "details": {
          "meta_json_valid": true,
          "scorer_exists": true,
          "resources_valid": true
        }
      }
    },
    "warnings": [
      "Output directory is empty - no prediction results found"
    ],
    "errors": [],
    "suggestions": [
      "Consider adding logging configuration to meta.json"
    ]
  }
}
```

### 初始化工作区

创建标准的工作区结构。

```http
POST /api/v1/workspaces/init
```

**请求体:**

```json
{
  "workspace_path": "/path/to/new/workspace",
  "template": "classification",     // 模板类型
  "job_id": "job-001",             // 可选
  "task_type": "classification",
  "scorer": "classification_f1",
  "config": {                      // 可选配置
    "time_limit": 1800,
    "resources": {
      "cpu": 2.0,
      "memory": "4Gi"
    }
  }
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "workspace_path": "/path/to/new/workspace",
    "template_used": "classification",
    "created_files": [
      "meta.json",
      "input/.gitkeep",
      "output/.gitkeep", 
      "logs/.gitkeep"
    ],
    "structure": {
      "input/": "Input data directory (read-only)",
      "output/": "Output results directory (read-write)",
      "logs/": "Execution logs directory (read-write)",
      "meta.json": "Job configuration file"
    },
    "next_steps": [
      "Place your ground truth data in input/gt.csv",
      "Place your model predictions in output/pred.csv",
      "Run evaluation with: autoscorer score /path/to/new/workspace"
    ]
  }
}
```

## 配置管理 API

### 获取系统配置

获取当前系统配置。

```http
GET /api/v1/config
```

**查询参数:**
- `section`: 配置段落 (executor|redis|api|logging)
- `include_defaults`: 是否包含默认值

**响应示例:**

```json
{
  "success": true,
  "data": {
    "executor": {
      "type": "docker",
      "docker": {
        "network_mode": "bridge",
        "cleanup": true,
        "timeout": 3600
      },
      "k8s": {
        "enabled": false,
        "namespace": "autoscorer"
      }
    },
    "redis": {
      "url": "redis://localhost:6379/0",
      "max_connections": 10
    },
    "api": {
      "host": "0.0.0.0",
      "port": 8000,
      "workers": 4
    },
    "logging": {
      "level": "INFO",
      "format": "json"
    }
  }
}
```

### 更新配置

更新系统配置(需要管理员权限)。

```http
PUT /api/v1/config
```

**请求体:**

```json
{
  "section": "executor",  // 配置段落
  "config": {
    "type": "k8s",
    "k8s": {
      "enabled": true,
      "namespace": "autoscorer-prod"
    }
  },
  "restart_required": true  // 是否需要重启服务
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "updated_section": "executor",
    "changes": {
      "type": {
        "old": "docker",
        "new": "k8s"
      },
      "k8s.enabled": {
        "old": false,
        "new": true
      }
    },
    "restart_required": true,
    "updated_at": "2024-08-24T10:00:00Z"
  }
}
```

## 批量操作 API

### 批量任务状态查询

查询多个任务的状态。

```http
POST /api/v1/jobs/batch/status
```

**请求体:**

```json
{
  "job_ids": ["job-001", "job-002", "job-003"],
  "include_progress": true
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "job_id": "job-001",
        "status": "completed",
        "progress": 1.0,
        "score": 0.85
      },
      {
        "job_id": "job-002", 
        "status": "running",
        "progress": 0.65,
        "estimated_completion": "2024-08-24T10:15:00Z"
      },
      {
        "job_id": "job-003",
        "status": "failed",
        "error": "Invalid workspace format"
      }
    ],
    "summary": {
      "total": 3,
      "completed": 1,
      "running": 1,
      "failed": 1
    }
  }
}
```

### 批量取消任务

取消多个任务。

```http
DELETE /api/v1/jobs/batch
```

**请求体:**

```json
{
  "job_ids": ["job-001", "job-002"],
  "reason": "User requested batch cancellation"
}
```

**响应示例:**

```json
{
  "success": true,
  "data": {
    "cancelled_jobs": [
      {
        "job_id": "job-001",
        "status": "cancelled",
        "cancelled_at": "2024-08-24T10:00:00Z"
      },
      {
        "job_id": "job-002",
        "status": "cancelled", 
        "cancelled_at": "2024-08-24T10:00:00Z"
      }
    ],
    "failed_cancellations": [],
    "total_cancelled": 2
  }
}
```

## 错误处理

### 错误响应格式

```json
{
  "success": false,
  "data": null,
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "request_id": "req_abc123",
    "api_version": "v1"
  },
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Invalid workspace structure", 
      "field": "workspace_path",
      "details": {
        "missing_files": ["input/gt.csv"],
        "workspace_path": "/invalid/path"
      }
    }
  ]
}
```

### 常见错误码

| 错误码 | HTTP状态码 | 描述 | 解决方案 |
|--------|------------|------|----------|
| `INVALID_PARAMETER` | 400 | 请求参数无效 | 检查参数格式和值 |
| `MISSING_PARAMETER` | 400 | 缺少必需参数 | 添加必需的参数 |
| `VALIDATION_ERROR` | 422 | 数据验证失败 | 修复数据格式问题 |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 | 确认资源路径正确 |
| `SCORER_NOT_FOUND` | 404 | 评分器不存在 | 使用有效的评分器名称 |
| `WORKSPACE_INVALID` | 422 | 工作区格式无效 | 修复工作区结构 |
| `EXECUTION_FAILED` | 500 | 执行失败 | 检查日志和配置 |
| `TIMEOUT_ERROR` | 408 | 请求超时 | 增加超时时间或优化任务 |
| `QUOTA_EXCEEDED` | 429 | 配额超限 | 等待或请求配额增加 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 | 稍后重试或联系管理员 |

### 错误处理最佳实践

```python
import requests
import time

def call_api_with_retry(url, data=None, max_retries=3):
    """带重试的 API 调用示例"""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data)
            
            # 检查HTTP状态码
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # 请求限流，等待后重试
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            elif response.status_code >= 500:
                # 服务器错误，重试
                print(f"Server error {response.status_code}, retrying...")
                time.sleep(2 ** attempt)
                continue
            else:
                # 客户端错误，不重试
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            print(f"Request failed: {e}, retrying...")
            time.sleep(2 ** attempt)
    
    raise Exception("Max retries exceeded")

# 使用示例
try:
    result = call_api_with_retry(
        "http://localhost:8000/api/v1/jobs",
        data={"job_id": "test", "task_type": "classification"}
    )
    print(f"Job submitted: {result['data']['job_id']}")
    
except Exception as e:
    print(f"API call failed: {e}")
```

## SDK 和客户端库

### Python SDK 示例

```python
from autoscorer_client import AutoScorerClient

# 创建客户端
client = AutoScorerClient(base_url="http://localhost:8000")

# 提交任务
job = client.submit_job(
    job_id="sdk-test-001",
    task_type="classification",
    scorer="classification_f1",
    workspace_path="/path/to/workspace"
)

# 等待完成
result = client.wait_for_completion(job.job_id, timeout=300)

# 获取结果
if result.success:
    print(f"Score: {result.data.result.summary.score}")
else:
    print(f"Job failed: {result.errors}")

# 批量操作
jobs = client.submit_batch([
    {"job_id": "batch-001", "workspace_path": "/workspace1"},
    {"job_id": "batch-002", "workspace_path": "/workspace2"}
])

# 监控进度
for job_id in jobs.job_ids:
    status = client.get_job_status(job_id)
    print(f"{job_id}: {status.status} ({status.progress}%)")
```

### JavaScript SDK 示例

```javascript
import { AutoScorerClient } from 'autoscorer-js-client';

const client = new AutoScorerClient({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your-api-key'  // 可选
});

// 提交任务
const job = await client.submitJob({
  jobId: 'js-test-001',
  taskType: 'classification',
  scorer: 'classification_f1',
  workspacePath: '/path/to/workspace'
});

// 监控状态
const status = await client.getJobStatus(job.jobId);
console.log(`Status: ${status.status}, Progress: ${status.progress}%`);

// 获取结果
if (status.status === 'completed') {
  const result = await client.getJobResult(job.jobId);
  console.log(`Score: ${result.summary.score}`);
}

// 流式日志
client.streamLogs(job.jobId, (logEntry) => {
  console.log(`[${logEntry.timestamp}] ${logEntry.level}: ${logEntry.message}`);
});
```

## 性能优化建议

### 1. 批量操作

```python
# 推荐：使用批量 API
jobs = client.submit_batch(job_list)

# 不推荐：逐个提交
for job_data in job_list:
    client.submit_job(job_data)
```

### 2. 异步处理

```python
# 对于长时间运行的任务，使用异步模式
job = client.submit_job(data, async=True)

# 定期检查状态而不是阻塞等待
while True:
    status = client.get_job_status(job.job_id)
    if status.status in ['completed', 'failed']:
        break
    time.sleep(5)
```

### 3. 合理的轮询间隔

```python
# 根据任务类型调整轮询间隔
if task_is_quick:
    poll_interval = 1  # 快速任务 1 秒轮询
else:
    poll_interval = 10  # 长任务 10 秒轮询
```

### 4. 连接池和会话复用

```python
import requests

# 使用会话复用连接
session = requests.Session()
session.headers.update({'Authorization': 'Bearer token'})

# 所有请求使用同一个会话
response = session.post('/api/v1/jobs', json=data)
```

## 相关文档

- **[快速开始](getting-started.md)** - 快速上手指南
- **[CLI 指南](cli-guide.md)** - 命令行工具使用
- **[工作区规范](workspace-spec.md)** - 数据格式要求
- **[评分算法详解](scoring-algorithms.md)** - 评分器使用指南
- **[部署指南](deployment.md)** - 生产环境部署
