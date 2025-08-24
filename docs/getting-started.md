# 快速开始指南

本指南将帮助您在 5 分钟内启动并运行 AutoScorer 系统。

## 前置要求

### 系统要求
- **操作系统**: Linux/macOS/Windows
- **Python**: 3.10+ 
- **Docker**: 20.10+ (推荐)
- **内存**: 最少 4GB，推荐 8GB+
- **磁盘**: 最少 10GB 可用空间

### 依赖软件
- **Redis**: 消息队列服务 (5.0+)
- **Docker**: 容器执行引擎
- **Git**: 代码版本管理

## 安装方式

### 方式一：Docker Compose (推荐)

适合快速体验和开发环境。

```bash
# 1. 克隆代码
git clone <autoscorer-repo>
cd autoscorer

# 2. 启动服务
docker-compose up -d

# 3. 验证安装
curl http://localhost:8000/health
```

### 方式二：本地安装

适合生产环境或需要自定义配置的场景。

```bash
# 1. 克隆代码
git clone <autoscorer-repo>
cd autoscorer

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -e .

# 4. 启动 Redis
redis-server

# 5. 启动 Worker (新终端)
celery -A celery_app.worker worker --loglevel=info

# 6. 启动 API 服务 (新终端)
python -m autoscorer.api.run

# 7. 验证安装
curl http://localhost:8000/health
```

### 方式三：开发模式

适合开发和调试。

```bash
# 1. 克隆代码
git clone <autoscorer-repo>
cd autoscorer

# 2. 安装开发依赖
pip install -e ".[dev]"

# 3. 运行测试
pytest

# 4. 启动开发服务
python -m autoscorer.api.run --reload
```

## 第一个评分任务

### 1. 准备工作区

```bash
# 创建示例工作区
mkdir -p /tmp/demo-workspace/{input,output,logs}

# 准备输入数据
cat > /tmp/demo-workspace/input/gt.csv << EOF
id,label
1,0
2,1
3,0
4,1
5,0
EOF

# 准备预测结果
cat > /tmp/demo-workspace/output/pred.csv << EOF
id,label
1,0
2,1
3,1
4,1
5,0
EOF

# 创建任务配置
cat > /tmp/demo-workspace/meta.json << EOF
{
  "job_id": "demo-001",
  "task_type": "classification",
  "scorer": "classification_f1",
  "time_limit": 300,
  "resources": {
    "cpu": 1.0,
    "memory": "1Gi"
  }
}
EOF
```

### 2. 执行评分

#### 使用 CLI

```bash
# 直接评分 (已有预测结果)
autoscorer score /tmp/demo-workspace

# 查看结果
cat /tmp/demo-workspace/output/result.json
```

#### 使用 API

```bash
# 提交评分任务
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "demo-001",
    "task_type": "classification", 
    "scorer": "classification_f1",
    "workspace_path": "/tmp/demo-workspace"
  }'

# 查询任务状态
curl http://localhost:8000/api/v1/jobs/demo-001/status

# 获取评分结果
curl http://localhost:8000/api/v1/jobs/demo-001/result
```

### 3. 理解结果

评分完成后，查看 `/tmp/demo-workspace/output/result.json`:

```json
{
  "summary": {
    "score": 0.8,
    "rank": "B+",
    "pass": true
  },
  "metrics": {
    "f1_macro": 0.8,
    "accuracy": 0.8,
    "precision": 0.8,
    "recall": 0.8
  },
  "artifacts": {},
  "timing": {
    "total_time": 0.05
  },
  "versioning": {
    "scorer": "classification_f1",
    "version": "2.0.0",
    "timestamp": "2024-08-24T10:30:00Z"
  }
}
```

**结果说明:**
- `score`: 综合得分 (0-1)
- `rank`: 等级评价
- `metrics`: 详细指标
- `timing`: 执行时间
- `versioning`: 版本信息

## 容器化评分

### 1. 准备容器化工作区

```bash
# 创建工作区
mkdir -p /tmp/container-demo/{input,output,logs}

# 准备数据
cp /tmp/demo-workspace/input/gt.csv /tmp/container-demo/input/

# 创建推理脚本
cat > /tmp/container-demo/inference.py << EOF
#!/usr/bin/env python3
import pandas as pd
import numpy as np

# 读取输入数据
gt = pd.read_csv('input/gt.csv')

# 模拟预测 (随机预测)
pred = gt.copy()
pred['label'] = np.random.choice([0, 1], size=len(gt))

# 保存预测结果
pred.to_csv('output/pred.csv', index=False)
print("预测完成!")
EOF

# 创建容器任务配置
cat > /tmp/container-demo/meta.json << EOF
{
  "job_id": "container-demo-001",
  "task_type": "classification",
  "scorer": "classification_f1",
  "time_limit": 300,
  "resources": {
    "cpu": 1.0,
    "memory": "1Gi"
  },
  "container": {
    "image": "python:3.10-slim",
    "cmd": ["python", "inference.py"],
    "env": {
      "PYTHONUNBUFFERED": "1"
    }
  }
}
EOF
```

### 2. 执行容器化评分

```bash
# 运行完整流程 (推理 + 评分)
autoscorer run /tmp/container-demo

# 查看日志
cat /tmp/container-demo/logs/container.log

# 查看结果
cat /tmp/container-demo/output/result.json
```

## 常用命令

### CLI 命令

```bash
# 查看帮助
autoscorer --help

# 查看可用评分器
autoscorer list-scorers

# 验证工作区
autoscorer validate /path/to/workspace

# 本地执行 (不使用容器)
autoscorer run /path/to/workspace --executor local

# 指定配置文件
autoscorer --config custom-config.yaml run /path/to/workspace

# 调试模式
autoscorer --debug run /path/to/workspace
```

### API 接口

```bash
# 系统状态
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status

# 评分器管理
curl http://localhost:8000/api/v1/scorers
curl http://localhost:8000/api/v1/scorers/classification_f1

# 任务管理
curl -X POST http://localhost:8000/api/v1/jobs -d @job.json
curl http://localhost:8000/api/v1/jobs
curl http://localhost:8000/api/v1/jobs/{job_id}
curl -X DELETE http://localhost:8000/api/v1/jobs/{job_id}
```

## 配置说明

### 基础配置 (config.yaml)

```yaml
# 执行器配置
executor:
  type: docker  # local, docker, k8s
  docker:
    network_mode: bridge
    cleanup: true
  
# Redis 配置
redis:
  url: redis://localhost:6379/0
  
# API 配置  
api:
  host: 0.0.0.0
  port: 8000
  
# 日志配置
logging:
  level: INFO
  format: json
```

### 环境变量

```bash
# Redis 连接
export REDIS_URL=redis://localhost:6379/0

# API 配置
export API_HOST=0.0.0.0
export API_PORT=8000

# 执行器配置
export EXECUTOR_TYPE=docker

# 日志级别
export LOG_LEVEL=INFO
```

## 故障排查

### 常见问题

#### 1. Redis 连接失败

**症状**: `ConnectionError: Error connecting to Redis`

**解决方案**:
```bash
# 检查 Redis 是否运行
redis-cli ping

# 启动 Redis
redis-server

# 检查配置
export REDIS_URL=redis://localhost:6379/0
```

#### 2. Docker 镜像拉取失败

**症状**: `Error pulling image`

**解决方案**:
```bash
# 手动拉取镜像
docker pull python:3.10-slim

# 使用镜像加速器
docker pull python:3.10-slim --registry-mirror=https://mirror.ccs.tencentyun.com
```

#### 3. 权限错误

**症状**: `Permission denied`

**解决方案**:
```bash
# 检查文件权限
ls -la /tmp/demo-workspace

# 修复权限
chmod -R 755 /tmp/demo-workspace

# 确保 Docker 可访问
sudo usermod -aG docker $USER
```

#### 4. 评分器未找到

**症状**: `Scorer 'xxx' not found`

**解决方案**:
```bash
# 查看可用评分器
autoscorer list-scorers

# 检查评分器注册
python -c "from autoscorer.scorers.registry import registry; print(registry.list_scorers())"
```

### 调试技巧

```bash
# 开启调试模式
export LOG_LEVEL=DEBUG

# 查看详细日志
autoscorer --debug run /path/to/workspace

# 验证工作区
autoscorer validate /path/to/workspace

# 测试评分器
python -c "
from autoscorer.scorers.registry import get_scorer
scorer = get_scorer('classification_f1')
print(scorer.name, scorer.version)
"
```

## 下一步

现在您已经成功运行了第一个评分任务！接下来可以：

1. **[学习工作区规范](workspace-spec.md)** - 了解数据格式要求
2. **[探索评分算法](scoring-algorithms.md)** - 使用不同评分器
3. **[开发自定义评分器](custom-scorers.md)** - 扩展评分能力
4. **[部署生产环境](deployment.md)** - 搭建生产级服务
5. **[API 集成指南](api-reference.md)** - 集成到您的系统

## 示例项目

在 `examples/` 目录下提供了完整的示例项目：

- `classification/` - 分类任务示例
- `regression/` - 回归任务示例  
- `detection/` - 目标检测示例
- `hot_reload_test/` - 热重载功能演示

每个示例都包含完整的工作区结构和说明文档，可以直接运行体验。
