# CLI 用户指南

本文档详细介绍 AutoScorer 命令行工具的使用方法，包括所有命令、选项和最佳实践。

## CLI 概述

AutoScorer CLI 是一个功能强大的命令行工具，提供完整的评分系统操作能力。通过 CLI，您可以执行评分任务、管理评分器、验证工作区。

### 主要功能

- **核心操作**: `run`、`score`、`pipeline` 命令
- **评分器管理**: `scorers` 命令（包含 list、load、reload、test 子命令）
- **工作区管理**: `validate` 命令
- **异步任务**: `submit` 命令
- **系统配置**: `config` 命令

## 安装和配置

### 安装方式

```bash
# 从源码安装
pip install -e .

# 验证安装
autoscorer --help
```

### 输出格式

所有 CLI 命令都使用统一的 JSON 输出格式：

**成功响应:**
```json
{
  "status": "success",
  "data": {
    // 具体数据
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "execution_time": 45.6,
  "workspace": "/path/to/workspace"
}
```

**错误响应:**
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid workspace structure",
    "stage": "validation"
  },
  "timestamp": "2024-08-24T10:00:00Z"
}
```

## 核心命令详解

### 1. validate 命令

验证工作区结构和 meta.json 配置文件。

#### 语法

```bash
autoscorer validate <workspace>
```

#### 示例

```bash
# 验证工作区结构
autoscorer validate /path/to/workspace
```

#### 输出示例

```json
{
  "status": "success",
  "data": {
    "validated": true,
    "job_id": "demo-job-001",
    "task_type": "classification"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "workspace": "/path/to/workspace"
}
```

### 2. run 命令

执行推理容器，生成预测结果（不包含评分）。

#### 语法

```bash
autoscorer run <workspace> [--backend BACKEND]
```

#### 选项

- `--backend`: 执行后端（docker|k8s|auto，默认：docker）

#### 示例

```bash
# 基本用法
autoscorer run /path/to/workspace

# 指定执行器
autoscorer run /path/to/workspace --backend docker

# 使用 k8s 执行器
autoscorer run /path/to/workspace --backend k8s
```

#### 输出示例

```json
{
  "status": "success",
  "data": {
    "run_result": "执行成功"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "execution_time": 45.6,
  "workspace": "/path/to/workspace",
  "backend_used": "docker"
}
```

### 3. score 命令

对现有预测结果进行评分。

#### 语法

```bash
autoscorer score <workspace> [--params PARAMS] [--scorer SCORER]
```

#### 选项

- `--params`: JSON字符串，评分器参数
- `--scorer`: 指定使用的评分器名称

#### 示例

```bash
# 基本评分
autoscorer score /path/to/workspace

# 指定评分器
autoscorer score /path/to/workspace --scorer classification_f1

# 使用评分器参数
autoscorer score /path/to/workspace \
  --scorer classification_f1 \
  --params '{"average": "macro"}'

# 回归任务评分
autoscorer score /path/to/workspace \
  --scorer regression_rmse \
  --params '{"sample_weight": null}'
```

#### 输出示例

```json
{
  "status": "success",
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
    "output_path": "/path/to/workspace/output/result.json"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "execution_time": 3.5,
  "workspace": "/path/to/workspace",
  "scorer_used": "classification_f1"
}
```

### 4. pipeline 命令

执行完整的推理+评分流水线。

#### 语法

```bash
autoscorer pipeline <workspace> [--backend BACKEND] [--params PARAMS] [--scorer SCORER]
```

#### 选项

- `--backend`: 执行后端（docker|k8s|auto，默认：docker）
- `--params`: JSON字符串，评分器参数
- `--scorer`: 指定使用的评分器名称

#### 示例

```bash
# 基本用法
autoscorer pipeline /path/to/workspace

# 完整参数
autoscorer pipeline /path/to/workspace \
  --backend docker \
  --scorer classification_f1 \
  --params '{"average": "macro"}'
```

#### 输出示例

```json
{
  "status": "success",
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
    }
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "execution_time": 48.1,
  "workspace": "/path/to/workspace",
  "backend_used": "docker",
  "scorer_used": "classification_f1"
}
```

### 5. submit 命令

提交异步任务到 Celery 队列。

#### 语法

```bash
autoscorer submit <workspace> [--action ACTION] [--params PARAMS]
```

#### 选项

- `--action`: 执行动作（run|score|pipeline，默认：run）
- `--params`: JSON字符串，评分器参数

#### 示例

```bash
# 提交运行任务
autoscorer submit /path/to/workspace --action run

# 提交评分任务
autoscorer submit /path/to/workspace \
  --action score \
  --params '{"average": "macro"}'

# 提交流水线任务
autoscorer submit /path/to/workspace \
  --action pipeline \
  --params '{"average": "weighted"}'
```

#### 输出示例

```json
{
  "status": "success",
  "data": {
    "submitted": true,
    "task_id": "celery-task-abc123",
    "action": "pipeline",
    "params": {
      "average": "weighted"
    }
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "workspace": "/path/to/workspace"
}
```

## 评分器管理

### scorers 命令

管理评分器的统一命令，包含多个子命令。

#### 列出所有评分器

```bash
autoscorer scorers list
```

**输出示例:**

```json
{
  "status": "success",
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
  "timestamp": "2024-08-24T10:00:00Z",
  "action": "scorers_list"
}
```

#### 加载自定义评分器

```bash
autoscorer scorers load --file-path /path/to/custom_scorer.py
```

**输出示例:**

```json
{
  "status": "success",
  "data": {
    "loaded": {
      "custom_nlp_scorer": "CustomNLPScorer"
    },
    "count": 1,
    "watching": true,
    "file_path": "/path/to/custom_scorer.py"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "action": "scorers_load"
}
```

#### 重新加载评分器

```bash
autoscorer scorers reload --file-path /path/to/custom_scorer.py
```

**输出示例:**

```json
{
  "status": "success", 
  "data": {
    "reloaded": {
      "custom_nlp_scorer": "CustomNLPScorer"
    },
    "count": 1,
    "file_path": "/path/to/custom_scorer.py"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "action": "scorers_reload"
}
```

#### 测试评分器

```bash
autoscorer scorers test \
  --scorer-name classification_f1 \
  --workspace /path/to/test/workspace
```

**输出示例:**

```json
{
  "status": "success",
  "data": {
    "scorer": "classification_f1",
    "class": "ClassificationF1Scorer",
    "result": {
      "summary": {
        "score": 0.85,
        "rank": "A",
        "pass": true
      },
      "versioning": {
        "scorer": "classification_f1",
        "version": "2.0.0"
      }
    }
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "action": "scorers_test",
  "workspace": "/path/to/test/workspace"
}
```

### 评分器开发工作流

```bash
# 1. 加载新的评分器文件
autoscorer scorers load --file-path my_scorer.py

# 2. 测试评分器
autoscorer scorers test \
  --scorer-name my_custom_scorer \
  --workspace examples/classification

# 3. 修改评分器后重新加载
autoscorer scorers reload --file-path my_scorer.py

# 4. 在实际任务中使用
autoscorer score /workspace --scorer my_custom_scorer
```

## 配置管理

### config 命令

管理系统配置的统一命令。

#### 显示配置

```bash
autoscorer config show [--config-path CONFIG_PATH]
```

**输出示例:**

```json
{
  "status": "success",
  "data": {
    "DOCKER_HOST": "unix:///var/run/docker.sock",
    "IMAGE_PULL_POLICY": "IfNotPresent",
    "DEFAULT_CPU": "2",
    "DEFAULT_MEMORY": "4Gi",
    "DEFAULT_GPU": "0",
    "TIMEOUT": "3600",
    "K8S_ENABLED": "false",
    "K8S_NAMESPACE": "autoscorer",
    "CELERY_BROKER": "redis://localhost:6379/0",
    "LOG_DIR": "/tmp/autoscorer",
    "WORKSPACE_ROOT": "/workspaces"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "config_file": "/path/to/config.yaml"
}
```

#### 验证配置

```bash
autoscorer config validate [--config-path CONFIG_PATH]
```

**成功输出:**

```json
{
  "status": "success",
  "data": {
    "validation": "passed"
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "config_file": "/path/to/config.yaml"
}
```

**失败输出:**

```json
{
  "status": "error",
  "error": {
    "code": "CONFIG_VALIDATION_ERROR",
    "message": "Found 2 configuration errors",
    "stage": "config_management",
    "details": {
      "errors": [
        "DOCKER_HOST is not accessible",
        "REDIS_URL connection failed"
      ]
    }
  },
  "timestamp": "2024-08-24T10:00:00Z"
}
```

#### 导出配置

```bash
autoscorer config dump [--config-path CONFIG_PATH]
```

**输出示例:**

```json
{
  "status": "success",
  "data": {
    "executor": {
      "type": "docker",
      "timeout": 3600
    },
    "logging": {
      "level": "INFO",
      "directory": "/tmp/autoscorer"
    },
    "celery": {
      "broker": "redis://localhost:6379/0"
    }
  },
  "timestamp": "2024-08-24T10:00:00Z",
  "config_file": "/path/to/config.yaml"
}
```

### 配置示例

#### 基础配置文件 (config.yaml)

```yaml
# 执行器配置
executor:
  type: docker
  timeout: 3600
  
# Docker 配置  
docker:
  host: unix:///var/run/docker.sock
  image_pull_policy: IfNotPresent
  cleanup: true
  
# K8s 配置
k8s:
  enabled: false
  namespace: autoscorer
  
# 资源默认值
resources:
  cpu: "2"
  memory: "4Gi"
  gpu: "0"
  
# Celery 配置
celery:
  broker: redis://localhost:6379/0
  backend: redis://localhost:6379/0
  
# 日志配置
logging:
  level: INFO
  directory: /tmp/autoscorer
  
# 工作区配置
workspace:
  root: /workspaces
  temp_dir: /tmp
```

#### 环境变量配置

```bash
# 设置配置文件路径
export AUTOSCORER_CONFIG="/path/to/config.yaml"

# 覆盖特定配置
export DOCKER_HOST="tcp://remote-docker:2376"
export REDIS_URL="redis://remote-redis:6379/0"
export LOG_LEVEL="DEBUG"
```

## 使用示例

### 基本工作流程

```bash
# 1. 验证工作区
autoscorer validate /path/to/workspace

# 2. 查看可用的评分器
autoscorer scorers list

# 3. 执行完整流水线
autoscorer pipeline /path/to/workspace \
  --scorer classification_f1 \
  --params '{"average": "macro"}'

# 4. 单独执行推理
autoscorer run /path/to/workspace

# 5. 单独执行评分
autoscorer score /path/to/workspace --scorer classification_f1
```

### 异步任务处理

```bash
# 1. 提交异步任务
autoscorer submit /path/to/workspace \
  --action pipeline \
  --params '{"average": "macro"}'

# 输出: {"status": "success", "data": {"task_id": "celery-task-abc123", ...}}

# 2. 通过 Celery 工具查询任务状态
celery -A celery_app.tasks inspect active

# 3. 或通过 API 查询
curl http://localhost:8000/tasks/celery-task-abc123
```

### 评分器开发

```bash
# 1. 创建自定义评分器文件
cat > my_scorer.py << 'EOF'
from autoscorer.scorers.base import BaseScorer
from autoscorer.schemas.result import Result, Summary
from pathlib import Path

@register_scorer("my_custom_scorer")
class MyCustomScorer(BaseScorer):
    def score(self, workspace: Path, params: dict) -> Result:
        # 实现评分逻辑
        return Result(
            summary=Summary(score=0.85, rank="A", pass=True),
            # ...
        )
EOF

# 2. 加载评分器
autoscorer scorers load --file-path my_scorer.py

# 3. 测试评分器
autoscorer scorers test \
  --scorer-name my_custom_scorer \
  --workspace examples/classification

# 4. 使用自定义评分器
autoscorer score /workspace --scorer my_custom_scorer
```

### 配置管理

```bash
# 1. 查看当前配置
autoscorer config show

# 2. 验证配置
autoscorer config validate

# 3. 导出配置进行备份
autoscorer config dump > config-backup.json

# 4. 使用自定义配置文件
autoscorer config show --config-path /path/to/custom-config.yaml
```

## 脚本集成

### Bash 脚本示例

```bash
#!/bin/bash
# evaluate.sh - 自动化评估脚本

set -e

WORKSPACE="${1:-/workspace}"
SCORER="${2:-classification_f1}"
THRESHOLD="${3:-0.8}"

echo "Starting evaluation..."
echo "Workspace: $WORKSPACE"
echo "Scorer: $SCORER"
echo "Threshold: $THRESHOLD"

# 验证工作区
echo "Validating workspace..."
if ! autoscorer validate "$WORKSPACE" > /dev/null 2>&1; then
    echo "❌ Workspace validation failed"
    exit 1
fi

# 执行评分
echo "Running evaluation..."
RESULT=$(autoscorer score "$WORKSPACE" --scorer "$SCORER")
STATUS=$(echo "$RESULT" | jq -r '.status')

if [ "$STATUS" = "success" ]; then
    SCORE=$(echo "$RESULT" | jq -r '.data.score_result.summary.score')
    echo "Evaluation completed. Score: $SCORE"
    
    # 检查阈值
    if (( $(echo "$SCORE >= $THRESHOLD" | bc -l) )); then
        echo "✅ Passed (Score: $SCORE >= $THRESHOLD)"
        exit 0
    else
        echo "❌ Failed (Score: $SCORE < $THRESHOLD)"
        exit 1
    fi
else
    ERROR_MSG=$(echo "$RESULT" | jq -r '.error.message')
    echo "❌ Evaluation failed: $ERROR_MSG"
    exit 1
fi
```

### Python 集成示例

```python
import subprocess
import json
import sys
from pathlib import Path

def run_autoscorer(workspace: str, scorer: str = "classification_f1") -> dict:
    """运行 AutoScorer 评分"""
    cmd = [
        "autoscorer", "score", workspace,
        "--scorer", scorer
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        return json.loads(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print(f"AutoScorer failed: {e.stderr}")
        return {"status": "error", "error": {"message": str(e)}}
    except json.JSONDecodeError as e:
        print(f"Failed to parse result: {e}")
        return {"status": "error", "error": {"message": "Invalid JSON output"}}

def validate_workspace(workspace: str) -> bool:
    """验证工作区"""
    cmd = ["autoscorer", "validate", workspace]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
        data = json.loads(result.stdout)
        return data.get("status") == "success"
    except:
        return False

# 使用示例
if __name__ == "__main__":
    workspace = "/path/to/workspace"
    
    # 1. 验证工作区
    if not validate_workspace(workspace):
        print("❌ Workspace validation failed")
        sys.exit(1)
    
    # 2. 执行评分
    result = run_autoscorer(workspace)
    
    if result.get("status") == "success":
        score = result["data"]["score_result"]["summary"]["score"]
        print(f"Score: {score}")
        
        if score >= 0.8:
            print("✅ Passed")
            sys.exit(0)
        else:
            print("❌ Failed")
            sys.exit(1)
    else:
        error_msg = result.get("error", {}).get("message", "Unknown error")
        print(f"❌ Evaluation error: {error_msg}")
        sys.exit(1)
```

## 常见问题排查

### 1. 工作区验证失败

```bash
# 检查工作区结构
autoscorer validate /workspace

# 常见错误和解决方案：
# - 缺少 meta.json: 检查文件是否存在
# - JSON 格式错误: 验证 JSON 语法
# - 缺少必要目录: 创建 input/、output/ 目录
```

### 2. 评分器未找到

```bash
# 查看可用评分器
autoscorer scorers list

# 加载自定义评分器
autoscorer scorers load --file-path /path/to/scorer.py

# 重新加载评分器
autoscorer scorers reload --file-path /path/to/scorer.py
```

### 3. 执行失败

```bash
# 检查配置
autoscorer config show

# 验证配置
autoscorer config validate

# 查看详细错误信息（通过 JSON 输出）
autoscorer run /workspace 2>&1 | jq '.error'
```

### 4. 异步任务问题

```bash
# 确保 Celery worker 正在运行
celery -A celery_app.worker worker --loglevel=info

# 检查 Redis 连接
redis-cli ping

# 查看任务状态
celery -A celery_app.tasks inspect active
```

## 相关文档

- **[API 参考](api-reference.md)** - REST API 详细文档
- **[工作区规范](workspace-spec.md)** - 数据格式要求
- **[评分器开发](scorer-development.md)** - 自定义评分器开发
- **[部署指南](DEPLOYMENT.md)** - 生产环境部署
