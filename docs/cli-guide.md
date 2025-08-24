# CLI 用户指南

本文档详细介绍 AutoScorer 命令行工具的使用方法，包括所有命令、选项和最佳实践。

## CLI 概述

AutoScorer CLI 是一个功能强大的命令行工具，提供完整的评分系统操作能力。通过 CLI，您可以执行评分任务、管理评分器、验证工作区，以及进行系统配置。

### 主要功能

- **评分操作**: `run`、`score`、`pipeline` 命令
- **评分器管理**: `list-scorers`、`describe-scorer` 命令  
- **工作区管理**: `validate`、`init-workspace` 命令
- **系统配置**: `config`、`status` 命令
- **调试工具**: `debug`、`test` 命令

## 安装和配置

### 安装方式

```bash
# 方式一：从源码安装
pip install -e .

# 方式二：使用开发模式
pip install -e ".[dev]"

# 验证安装
autoscorer --version
autoscorer --help
```

### 基础配置

```bash
# 查看当前配置
autoscorer config show

# 设置 Redis 连接
autoscorer config set redis.url redis://localhost:6379/0

# 设置默认执行器
autoscorer config set executor.type docker

# 设置日志级别
autoscorer config set logging.level INFO
```

### 环境变量

```bash
# 配置环境变量
export AUTOSCORER_CONFIG="/path/to/config.yaml"
export REDIS_URL="redis://localhost:6379/0"
export LOG_LEVEL="INFO"
export EXECUTOR_TYPE="docker"

# 验证环境
autoscorer status
```

## 核心命令详解

### 1. run 命令

执行完整的"推理+评分"流程。

#### 基本语法

```bash
autoscorer run <workspace> [options]
```

#### 常用示例

```bash
# 基本用法
autoscorer run /path/to/workspace

# 指定执行器
autoscorer run /path/to/workspace --executor docker

# 本地执行（不使用容器）
autoscorer run /path/to/workspace --executor local

# 使用自定义配置
autoscorer run /path/to/workspace --config custom-config.yaml

# 调试模式
autoscorer run /path/to/workspace --debug

# 指定超时时间
autoscorer run /path/to/workspace --timeout 3600

# 覆盖资源限制
autoscorer run /path/to/workspace --cpu 4.0 --memory 8Gi

# 同步执行（等待完成）
autoscorer run /path/to/workspace --sync

# 异步执行（后台运行）
autoscorer run /path/to/workspace --async
```

#### 高级选项

```bash
# 指定作业ID
autoscorer run /path/to/workspace --job-id custom-job-001

# 强制重新运行
autoscorer run /path/to/workspace --force

# 仅验证不执行
autoscorer run /path/to/workspace --dry-run

# 保留容器（调试用）
autoscorer run /path/to/workspace --keep-container

# 使用GPU
autoscorer run /path/to/workspace --gpus 1

# 网络策略
autoscorer run /path/to/workspace --network-policy restricted

# 自定义环境变量
autoscorer run /path/to/workspace --env CUDA_VISIBLE_DEVICES=0 --env PYTHONPATH=/workspace
```

### 2. score 命令

仅执行评分步骤，假设预测结果已存在。

#### 基本语法

```bash
autoscorer score <workspace> [options]
```

#### 常用示例

```bash
# 基本评分
autoscorer score /path/to/workspace

# 指定评分器
autoscorer score /path/to/workspace --scorer classification_f1

# 使用评分参数
autoscorer score /path/to/workspace --scorer-params '{"average": "macro"}'

# 输出详细结果
autoscorer score /path/to/workspace --verbose

# 保存结果到文件
autoscorer score /path/to/workspace --output result.json

# 多个工作区批量评分
autoscorer score workspace1/ workspace2/ workspace3/

# 并行评分
autoscorer score /path/to/workspace --parallel --workers 4
```

#### 评分参数示例

```bash
# 分类任务参数
autoscorer score /path/to/workspace \
  --scorer classification_f1 \
  --scorer-params '{
    "average": "macro",
    "labels": [0, 1, 2],
    "sample_weight": null
  }'

# 回归任务参数  
autoscorer score /path/to/workspace \
  --scorer regression_rmse \
  --scorer-params '{
    "sample_weight": null,
    "multioutput": "uniform_average"
  }'

# 检测任务参数
autoscorer score /path/to/workspace \
  --scorer detection_map \
  --scorer-params '{
    "iou_thresholds": [0.5, 0.75, 0.9],
    "area_ranges": [[0, 32], [32, 96], [96, 10000000000]]
  }'
```

### 3. pipeline 命令

执行自定义流水线任务。

#### 基本语法

```bash
autoscorer pipeline <workspace> [options]
```

#### 示例用法

```bash
# 执行预定义流水线
autoscorer pipeline /path/to/workspace --pipeline-name standard

# 自定义流水线步骤
autoscorer pipeline /path/to/workspace \
  --steps preprocess,inference,postprocess,score

# 跳过某些步骤
autoscorer pipeline /path/to/workspace --skip-steps preprocess

# 从指定步骤开始
autoscorer pipeline /path/to/workspace --start-from inference

# 流水线参数
autoscorer pipeline /path/to/workspace \
  --pipeline-params '{
    "preprocess": {"normalize": true},
    "inference": {"batch_size": 32},
    "score": {"threshold": 0.8}
  }'
```

## 评分器管理

### 查看可用评分器

```bash
# 列出所有评分器
autoscorer list-scorers

# 按类型过滤
autoscorer list-scorers --type classification

# 显示详细信息
autoscorer list-scorers --verbose

# 搜索评分器
autoscorer list-scorers --search f1

# 输出格式
autoscorer list-scorers --format json
autoscorer list-scorers --format table
autoscorer list-scorers --format yaml
```

### 评分器详细信息

```bash
# 查看评分器详情
autoscorer describe-scorer classification_f1

# 查看特定版本
autoscorer describe-scorer classification_f1 --version 2.0.0

# 显示使用示例
autoscorer describe-scorer classification_f1 --examples

# 显示支持的参数
autoscorer describe-scorer classification_f1 --parameters
```

### 评分器测试

```bash
# 测试评分器
autoscorer test-scorer classification_f1 \
  --workspace examples/classification

# 测试所有评分器
autoscorer test-scorers --workspace examples/

# 性能测试
autoscorer benchmark-scorer classification_f1 \
  --workspace examples/classification \
  --iterations 10
```

## 工作区管理

### 工作区验证

```bash
# 验证工作区结构
autoscorer validate /path/to/workspace

# 详细验证报告
autoscorer validate /path/to/workspace --verbose

# 检查特定组件
autoscorer validate /path/to/workspace --check-data
autoscorer validate /path/to/workspace --check-config
autoscorer validate /path/to/workspace --check-structure

# 修复常见问题
autoscorer validate /path/to/workspace --fix

# 批量验证
autoscorer validate workspace1/ workspace2/ workspace3/
```

### 工作区初始化

```bash
# 创建新工作区
autoscorer init-workspace /path/to/new-workspace

# 使用模板
autoscorer init-workspace /path/to/new-workspace \
  --template classification

# 指定任务类型
autoscorer init-workspace /path/to/new-workspace \
  --task-type regression \
  --scorer regression_rmse

# 完整配置
autoscorer init-workspace /path/to/new-workspace \
  --template classification \
  --job-id demo-job-001 \
  --scorer classification_f1 \
  --time-limit 1800 \
  --cpu 2.0 \
  --memory 4Gi
```

### 工作区模板

```bash
# 列出可用模板
autoscorer list-templates

# 查看模板详情
autoscorer describe-template classification

# 从现有工作区创建模板
autoscorer create-template /path/to/workspace \
  --name my-template \
  --description "My custom template"

# 应用模板
autoscorer apply-template my-template /path/to/workspace
```

## 系统管理

### 系统状态

```bash
# 查看系统状态
autoscorer status

# 详细状态信息
autoscorer status --verbose

# 检查连接状态
autoscorer status --check-redis
autoscorer status --check-docker
autoscorer status --check-k8s

# 健康检查
autoscorer health-check

# 系统信息
autoscorer system-info
```

### 配置管理

```bash
# 显示当前配置
autoscorer config show

# 显示配置文件位置
autoscorer config location

# 编辑配置文件
autoscorer config edit

# 设置配置项
autoscorer config set executor.type docker
autoscorer config set redis.url redis://localhost:6379/1

# 获取配置项
autoscorer config get executor.type

# 重置配置
autoscorer config reset

# 验证配置
autoscorer config validate

# 导出配置
autoscorer config export --output config-backup.yaml

# 导入配置
autoscorer config import config-backup.yaml
```

### 缓存管理

```bash
# 清理缓存
autoscorer cache clear

# 查看缓存统计
autoscorer cache stats

# 清理特定类型缓存
autoscorer cache clear --type images
autoscorer cache clear --type results
autoscorer cache clear --type scorers

# 缓存预热
autoscorer cache warm --scorer classification_f1
```

## 调试和开发

### 调试模式

```bash
# 开启调试模式
autoscorer --debug run /path/to/workspace

# 详细日志
autoscorer --log-level DEBUG run /path/to/workspace

# 保存日志到文件
autoscorer run /path/to/workspace --log-file debug.log

# 交互式调试
autoscorer debug /path/to/workspace

# 步进执行
autoscorer debug /path/to/workspace --step-by-step
```

### 开发工具

```bash
# 代码生成
autoscorer generate scorer --name my_scorer --type classification

# 代码检查
autoscorer lint /path/to/custom_scorer.py

# 运行测试
autoscorer test --workspace examples/

# 性能分析
autoscorer profile run /path/to/workspace

# 内存分析
autoscorer profile memory /path/to/workspace
```

### 热重载开发

```bash
# 加载自定义评分器
autoscorer load-scorer /path/to/custom_scorer.py

# 启用文件监控
autoscorer watch-scorer /path/to/custom_scorer.py

# 重新加载评分器
autoscorer reload-scorer my_custom_scorer

# 停止监控
autoscorer unwatch-scorer /path/to/custom_scorer.py

# 查看监控状态
autoscorer watch-status
```

## 输出格式和选项

### 输出格式

```bash
# JSON 格式
autoscorer score /path/to/workspace --format json

# YAML 格式  
autoscorer score /path/to/workspace --format yaml

# 表格格式
autoscorer score /path/to/workspace --format table

# CSV 格式
autoscorer score /path/to/workspace --format csv

# 自定义格式
autoscorer score /path/to/workspace --format custom \
  --template "Score: {{summary.score}}, Rank: {{summary.rank}}"
```

### 输出控制

```bash
# 静默模式
autoscorer run /path/to/workspace --quiet

# 详细输出
autoscorer run /path/to/workspace --verbose

# 仅显示错误
autoscorer run /path/to/workspace --errors-only

# 进度条
autoscorer run /path/to/workspace --progress

# 彩色输出
autoscorer run /path/to/workspace --color

# 无彩色输出
autoscorer run /path/to/workspace --no-color
```

### 结果输出

```bash
# 保存结果到文件
autoscorer score /path/to/workspace --output result.json

# 结果目录
autoscorer score /path/to/workspace --output-dir results/

# 追加模式
autoscorer score /path/to/workspace --output result.json --append

# 压缩输出
autoscorer score /path/to/workspace --output result.json.gz --compress
```

## 批量操作

### 批量评分

```bash
# 多个工作区
autoscorer score workspace1/ workspace2/ workspace3/

# 通配符模式
autoscorer score workspaces/*/

# 从文件列表
autoscorer score --workspace-list workspaces.txt

# 并行处理
autoscorer score workspaces/*/ --parallel --workers 4

# 失败重试
autoscorer score workspaces/*/ --retry 3 --retry-delay 5
```

### 批量验证

```bash
# 批量验证工作区
autoscorer validate workspaces/*/

# 生成验证报告
autoscorer validate workspaces/*/ --report validation-report.html

# 仅显示失败项
autoscorer validate workspaces/*/ --failures-only

# 修复所有工作区
autoscorer validate workspaces/*/ --fix-all
```

### 批量初始化

```bash
# 批量创建工作区
autoscorer batch-init \
  --template classification \
  --count 10 \
  --base-path experiments/ \
  --prefix exp-

# 从配置文件批量创建
autoscorer batch-init --config batch-config.yaml
```

## 集成和自动化

### CI/CD 集成

```bash
# 持续集成脚本示例
#!/bin/bash

# 1. 验证工作区
autoscorer validate /workspace --quiet || exit 1

# 2. 运行评分
autoscorer score /workspace --format json --output result.json

# 3. 检查通过条件
SCORE=$(jq -r '.summary.score' result.json)
if (( $(echo "$SCORE >= 0.8" | bc -l) )); then
    echo "Score $SCORE passed threshold"
    exit 0
else
    echo "Score $SCORE failed threshold"
    exit 1
fi
```

### 脚本化使用

```bash
# Bash 脚本示例
#!/bin/bash

WORKSPACE="/path/to/workspace"
SCORER="classification_f1"
THRESHOLD=0.8

# 运行评分
echo "Running evaluation..."
autoscorer score "$WORKSPACE" \
  --scorer "$SCORER" \
  --format json \
  --output result.json

# 检查结果
if [ $? -eq 0 ]; then
    SCORE=$(jq -r '.summary.score' result.json)
    echo "Evaluation completed. Score: $SCORE"
    
    if (( $(echo "$SCORE >= $THRESHOLD" | bc -l) )); then
        echo "✅ Passed (Score: $SCORE >= $THRESHOLD)"
        exit 0
    else
        echo "❌ Failed (Score: $SCORE < $THRESHOLD)" 
        exit 1
    fi
else
    echo "❌ Evaluation failed"
    exit 1
fi
```

### Python 集成

```python
# Python 集成示例
import subprocess
import json
import sys

def run_autoscorer(workspace, scorer="classification_f1"):
    """运行 AutoScorer 评分"""
    cmd = [
        "autoscorer", "score", workspace,
        "--scorer", scorer,
        "--format", "json"
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # 解析结果
        data = json.loads(result.stdout)
        return data
        
    except subprocess.CalledProcessError as e:
        print(f"AutoScorer failed: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Failed to parse result: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    workspace = "/path/to/workspace"
    result = run_autoscorer(workspace)
    
    if result:
        score = result["summary"]["score"]
        print(f"Score: {score}")
        
        if score >= 0.8:
            print("✅ Passed")
            sys.exit(0)
        else:
            print("❌ Failed")
            sys.exit(1)
    else:
        print("❌ Evaluation error")
        sys.exit(1)
```

## 配置文件详解

### 默认配置结构

```yaml
# config.yaml
# 执行器配置
executor:
  type: docker  # local, docker, k8s
  docker:
    network_mode: bridge
    cleanup: true
    timeout: 3600
  k8s:
    namespace: autoscorer
    service_account: autoscorer
    
# Redis 配置
redis:
  url: redis://localhost:6379/0
  max_connections: 10
  retry_attempts: 3

# API 配置
api:
  host: 0.0.0.0
  port: 8000
  workers: 4

# 日志配置
logging:
  level: INFO
  format: json
  file: autoscorer.log

# 评分器配置
scorers:
  auto_load: true
  search_paths:
    - custom_scorers/
    - /opt/autoscorer/scorers/
  hot_reload: true
  
# 缓存配置
cache:
  enabled: true
  ttl: 3600
  max_size: 1000
```

### 环境特定配置

```bash
# 开发环境
autoscorer --config config-dev.yaml run /workspace

# 测试环境
autoscorer --config config-test.yaml run /workspace

# 生产环境
autoscorer --config config-prod.yaml run /workspace
```

## 故障排查

### 常见问题和解决方案

#### 1. Redis 连接问题

```bash
# 检查 Redis 连接
autoscorer status --check-redis

# 如果连接失败，检查配置
autoscorer config get redis.url

# 测试 Redis 连接
redis-cli -u redis://localhost:6379/0 ping
```

#### 2. Docker 权限问题

```bash
# 检查 Docker 权限
docker ps

# 如果权限不足
sudo usermod -aG docker $USER
newgrp docker

# 验证权限
autoscorer status --check-docker
```

#### 3. 工作区格式问题

```bash
# 详细验证工作区
autoscorer validate /workspace --verbose

# 查看具体错误
autoscorer validate /workspace 2>&1 | grep ERROR

# 自动修复
autoscorer validate /workspace --fix
```

#### 4. 评分器未找到

```bash
# 检查可用评分器
autoscorer list-scorers

# 重新加载评分器
autoscorer reload-scorers

# 检查文件路径
autoscorer load-scorer /path/to/scorer.py
```

### 调试技巧

```bash
# 1. 开启详细日志
export LOG_LEVEL=DEBUG
autoscorer run /workspace --verbose

# 2. 保留临时文件
autoscorer run /workspace --keep-temp

# 3. 步进调试
autoscorer debug /workspace --step-by-step

# 4. 内存和性能分析
autoscorer profile run /workspace

# 5. 网络调试
autoscorer run /workspace --network-policy none
```

### 日志分析

```bash
# 查看系统日志
tail -f autoscorer.log

# 过滤错误日志
grep ERROR autoscorer.log

# 按时间范围查看
grep "2024-08-24" autoscorer.log

# 分析性能日志
grep "timing" autoscorer.log | jq '.timing'
```

## 最佳实践

### 1. 工作区组织

```bash
# 使用统一的目录结构
mkdir -p projects/{train,val,test}

# 为每个实验创建独立工作区
autoscorer init-workspace experiments/exp-001 --template classification
autoscorer init-workspace experiments/exp-002 --template regression
```

### 2. 配置管理

```bash
# 使用环境特定的配置文件
cp config.yaml config-prod.yaml
# 编辑 config-prod.yaml 适配生产环境

# 使用环境变量覆盖敏感配置
export REDIS_URL="redis://prod-redis:6379/0"
```

### 3. 批量处理

```bash
# 使用并行处理提高效率
autoscorer score experiments/*/ --parallel --workers $(nproc)

# 为大批量任务设置合理的超时
autoscorer score experiments/*/ --timeout 7200
```

### 4. 结果管理

```bash
# 统一的结果目录结构
mkdir -p results/{$(date +%Y-%m-%d)}

# 保存带时间戳的结果
autoscorer score /workspace \
  --output "results/$(date +%Y-%m-%d)/result-$(date +%H%M%S).json"
```

### 5. 自动化脚本

```bash
#!/bin/bash
# evaluate.sh - 自动化评估脚本

set -e

WORKSPACE="${1:-/workspace}"
SCORER="${2:-classification_f1}"
OUTPUT_DIR="${3:-results}"

echo "Starting evaluation..."
echo "Workspace: $WORKSPACE"
echo "Scorer: $SCORER"
echo "Output: $OUTPUT_DIR"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 验证工作区
echo "Validating workspace..."
autoscorer validate "$WORKSPACE"

# 执行评分
echo "Running evaluation..."
autoscorer score "$WORKSPACE" \
  --scorer "$SCORER" \
  --format json \
  --output "$OUTPUT_DIR/result.json" \
  --verbose

# 显示结果摘要
echo "Evaluation completed!"
jq -r '.summary' "$OUTPUT_DIR/result.json"
```

## 相关文档

- **[工作区规范](workspace-spec.md)** - 了解数据格式要求
- **[评分算法详解](scoring-algorithms.md)** - 学习评分器使用
- **[API 参考](api-reference.md)** - 程序化集成指南
- **[部署指南](deployment.md)** - 生产环境配置
- **[开发指南](development.md)** - 开发和调试技巧
