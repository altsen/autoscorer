# API 参考手册

本文档提供 AutoScorer REST API 的完整参考，包括所有端点、请求/响应格式、错误处理和使用示例。

## API 概述

AutoScorer API 是基于 REST 的 HTTP API，使用 JSON 进行数据交换。API 遵循 RESTful 设计原则，提供统一的接口用于任务提交、状态查询、评分器管理等功能。

### 基础信息

- **Base URL**: `http://localhost:8000`
- **API Version**: `0.1.0`
- **Content-Type**: `application/json`

### API 特性

- **统一响应格式**: 所有响应都使用标准化的格式
- **错误处理**: 详细的错误码和消息
- **异步支持**: 长时间运行的任务支持异步处理
- **热重载**: 支持评分器热重载和文件监控
- **工作区驱动配置**: backend 与 scorer 均由工作区 `meta.json` 决定，API 不再接收这两个字段作为请求参数

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
  "ok": true,
  "data": {
    // 具体数据内容
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "version": "0.1.0"
  }
}
```

#### 成功响应

```json
{
  "ok": true,
  "data": {
    "result": {
      "summary": {
        "score": 0.85
      }
    },
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "pipeline",
    "execution_time": 45.6
  }
}
```

#### 错误响应

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Invalid scorer name",
    "stage": "api",
    "details": {
      "provided": "invalid_scorer",
      "available": ["classification_f1", "regression_rmse"]
    }
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "version": "0.1.0"
  }
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
GET /healthz
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "status": "healthy"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0"
  }
}
```

## 核心执行 API

### 执行推理

执行推理容器，生成预测结果。

```http
POST /run
```

**请求体:**

```json
{
  "workspace": "/path/to/workspace"
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "run_result": "执行成功",
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "run_only",
    "execution_time": 45.6,
  "backend_used": "auto"
  }
}
```

### 执行评分

对现有预测结果进行评分。

```http
POST /score
```

**请求体:**

```json
{
  "workspace": "/path/to/workspace",
  "params": {
    "average": "macro"
  }
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "score_result": {
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
    "output_path": "/path/to/workspace/output/result.json",
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "score_only",
    "execution_time": 3.5,
  "scorer_used": "auto"
  }
}
```

### 执行完整流水线

执行推理+评分的完整流水线。

```http
POST /pipeline
```

**请求体:**

```json
{
  "workspace": "/path/to/workspace",
  "params": {
    "average": "macro"
  }
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "pipeline_result": {
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
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "pipeline",
    "execution_time": 48.1,
  "backend_used": "auto",
  "scorer_used": "auto"
  }
}
```

## 评分器管理 API

### 列出所有评分器

获取系统中可用的评分器列表。

```http
GET /scorers
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "scorers": {
      "classification_f1": {
        "name": "classification_f1", 
        "description": "F1-score for classification tasks",
        "task_type": "classification"
      },
      "regression_rmse": {
        "name": "regression_rmse",
        "description": "Root Mean Square Error for regression tasks", 
        "task_type": "regression"
      }
    },
    "total": 2,
    "watched_files": []
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0"
  }
}
```

### 加载自定义评分器

从文件加载自定义评分器。

```http
POST /scorers/load
```

**请求体:**

```json
{
  "file_path": "/path/to/custom_scorer.py",
  "auto_watch": true,      // 自动监控文件变化
  "force_reload": false    // 强制重新加载
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "loaded_scorers": {
      "custom_nlp_scorer": "CustomNLPScorer"
    },
    "count": 1,
    "auto_watch": true,
    "file_path": "/path/to/custom_scorer.py"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "load_scorer"
  }
}
```

### 重新加载评分器

重新加载指定的评分器文件。

```http
POST /scorers/reload
```

**请求体:**

```json
{
  "file_path": "/path/to/custom_scorer.py",
  "force_reload": false
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "reloaded_scorers": {
      "custom_nlp_scorer": "CustomNLPScorer"
    },
    "count": 1,
    "file_path": "/path/to/custom_scorer.py"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "reload_scorer"
  }
}
```

### 测试评分器

测试评分器在指定工作区上的运行效果。

```http
POST /scorers/test
```

**请求体:**

```json
{
  "scorer_name": "classification_f1",
  "workspace": "/path/to/test/workspace",
  "params": {
    "average": "macro"
  }
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "scorer_name": "classification_f1",
    "scorer_class": "ClassificationF1Scorer",
    "workspace": "/path/to/test/workspace",
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
    }
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "test_scorer",
    "execution_time": 0.45,
    "scorer_used": "classification_f1"
  }
}
```

### 监控评分器文件

开始监控评分器文件的变化。

```http
POST /scorers/watch
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
  "ok": true,
  "data": {
    "message": "Started watching /path/to/custom_scorer.py",
    "file_path": "/path/to/custom_scorer.py",
    "check_interval": 1.0
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "watch_start"
  }
}
```

### 停止监控评分器文件

停止监控特定文件。

```http
DELETE /scorers/watch?file_path=/path/to/custom_scorer.py
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "message": "Stopped watching /path/to/custom_scorer.py",
    "file_path": "/path/to/custom_scorer.py"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "watch_stop"
  }
}
```

### 查看监控状态

查看当前的文件监控状态。

```http
GET /scorers/watch
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "watched_files": [
      {
        "file_path": "/path/to/custom_scorer.py",
        "check_interval": 1.0,
        "started_at": "2024-08-24T10:00:00Z"
      }
    ],
    "count": 1
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "watch_list"
  }
}
```

## 结果和日志查询 API

### 获取执行结果

获取工作区的执行结果。

```http
GET /result?workspace=/path/to/workspace
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
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
    "path": "/path/to/workspace/output/result.json"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "get_result"
  }
}
```

### 获取执行日志

获取工作区的执行日志。

```http
GET /logs?workspace=/path/to/workspace
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "path": "/path/to/workspace/logs/container.log",
    "content": "2024-08-24 10:00:00 - INFO - Starting execution\n2024-08-24 10:01:00 - INFO - Execution completed"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "get_logs"
  }
}
```

## 异步任务管理 API

### 提交异步任务

提交异步执行任务。

```http
POST /submit
```

**请求体:**

```json
{
  "workspace": "/path/to/workspace",
  "action": "pipeline",        // run|score|pipeline
  "params": {},                 // 可选
  "callback_url": "http://callback.example.com/webhook" // 可选
}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "submitted": true,
    "task_id": "celery-task-abc123",
    "action": "pipeline",
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "submit"
  }
}
```

**去重响应示例:**

```json
{
  "ok": true,
  "data": {
    "submitted": false,
    "running": true,
    "task_id": "celery-task-existing",
    "action": "pipeline",
    "workspace": "/path/to/workspace"
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "submit_dedup"
  }
}
```

### 查询任务状态

查询异步任务的执行状态。

```http
GET /tasks/{task_id}
```

**响应示例:**

```json
{
  "ok": true,
  "data": {
    "id": "celery-task-abc123",
    "state": "SUCCESS",
    "result": {
      "summary": {
        "score": 0.85,
        "rank": "A",
        "pass": true
      }
    }
  },
  "meta": {
    "timestamp": "2025-08-24T10:00:00Z",
    "version": "0.1.0",
    "action": "task_status"
  }
}
```

## 错误处理

### 错误响应格式

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid workspace structure", 
    "stage": "execution",
    "details": {
      "missing_files": ["input/gt.csv"],
      "workspace": "/invalid/path"
    }
  },
  "meta": {
    "timestamp": "2024-08-24T10:00:00Z",
    "version": "0.1.0"
  }
}
```

### 常见错误码

| 错误码 | HTTP状态码 | 描述 | 解决方案 |
|--------|------------|------|----------|
| `INVALID_PARAMETER` | 400 | 请求参数无效 | 检查参数格式和值 |
| `FILE_NOT_FOUND` | 404 | 文件不存在 | 确认文件路径正确 |
| `SCORER_NOT_FOUND` | 404 | 评分器不存在 | 使用有效的评分器名称 |
| `VALIDATION_ERROR` | 422 | 数据验证失败 | 修复数据格式问题 |
| `EXEC_ERROR` | 500 | 执行失败 | 检查日志和配置 |
| `LOAD_ERROR` | 500 | 加载失败 | 检查文件格式和权限 |
| `PIPELINE_ERROR` | 500 | 流水线执行失败 | 检查工作区和配置 |
| `UNHANDLED_ERROR` | 500 | 未处理的错误 | 联系管理员 |

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
                result = response.json()
                if result.get("ok"):
                    return result
                else:
                    # API错误，不重试
                    raise Exception(f"API Error: {result.get('error', {}).get('message', 'Unknown error')}")
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
        "http://localhost:8000/pipeline",
        data={"workspace": "/path/to/workspace"}
    )
    print(f"Pipeline completed: {result['data']}")
    
except Exception as e:
    print(f"API call failed: {e}")
```

## 使用示例

### 基本工作流程

```python
import requests

# 1. 检查系统健康状态
health = requests.get("http://localhost:8000/healthz").json()
print(f"System status: {health['data']['status']}")

# 2. 列出可用的评分器
scorers = requests.get("http://localhost:8000/scorers").json()
print(f"Available scorers: {list(scorers['data']['scorers'].keys())}")

# 3. 执行完整流水线
pipeline_data = {
  "workspace": "/path/to/workspace",
  "params": {"average": "macro"}
}
result = requests.post("http://localhost:8000/pipeline", json=pipeline_data).json()

if result["ok"]:
    score = result["data"]["pipeline_result"]["summary"]["score"]
    print(f"Final score: {score}")
else:
    print(f"Error: {result['error']['message']}")
```

### 异步任务处理

```python
import requests
import time

# 1. 提交异步任务
submit_data = {
  "workspace": "/path/to/workspace",
  "action": "pipeline"
}
task = requests.post("http://localhost:8000/submit", json=submit_data).json()
task_id = task["data"]["task_id"]
print(f"Task submitted: {task_id}")

# 2. 监控任务状态
while True:
    status = requests.get(f"http://localhost:8000/tasks/{task_id}").json()
    state = status["data"]["state"]
    
    if state == "SUCCESS":
        result = status["data"]["result"]
        print(f"Task completed with score: {result['summary']['score']}")
        break
    elif state == "FAILURE":
        print(f"Task failed: {status['data'].get('result', 'Unknown error')}")
        break
    else:
        print(f"Task status: {state}")
        time.sleep(5)
```

### 动态评分器管理

```python
import requests

# 1. 加载自定义评分器
load_data = {
    "file_path": "/path/to/custom_scorer.py",
    "auto_watch": True
}
response = requests.post("http://localhost:8000/scorers/load", json=load_data)
print(f"Loaded scorers: {response.json()['data']['loaded_scorers']}")

# 2. 测试评分器
test_data = {
    "scorer_name": "custom_scorer",
    "workspace": "/path/to/test/workspace"
}
test_result = requests.post("http://localhost:8000/scorers/test", json=test_data)
print(f"Test result: {test_result.json()['data']['result']}")

# 3. 查看监控状态
watch_status = requests.get("http://localhost:8000/scorers/watch").json()
print(f"Watched files: {watch_status['data']['watched_files']}")
```

## 相关文档

- **[快速开始](getting-started.md)** - 快速上手指南
- **[CLI 指南](cli-guide.md)** - 命令行工具使用
- **[工作区规范](workspace-spec.md)** - 数据格式要求
- **[评分器开发](scorer-development.md)** - 自定义评分器开发
- **[部署指南](DEPLOYMENT.md)** - 生产环境部署
