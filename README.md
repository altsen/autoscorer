# AutoScorer

**版本:** v2.0  
**更新时间:** 2025年9月

一个生产就绪的容器化ML模型自动评分系统，支持分类、回归、检测等多种任务类型。

## 核心特性

- 🚀 **多后端执行**: 支持Docker、Kubernetes容器化执行
- 🔧 **插件化评分**: 动态注册评分器，支持热重载
- 📊 **标准化结果**: 统一的Result schema和错误处理
- 🔄 **异步任务**: 基于Celery的分布式任务队列
- 🌐 **RESTful API**: FastAPI提供完整的Web API接口
- 📁 **标准化IO**: 规范的工作区结构和数据格式
- 🛡️ **生产级**: 完善的错误处理、日志记录和监控

## 架构概览

```text
AutoScorer v2.0 Architecture
├── CLI Tools          # 命令行工具
├── FastAPI Server      # Web API服务
├── Pipeline Engine     # 执行管道
├── Executor Backends   # 执行后端 (Docker/K8s)
├── Scorer Registry     # 评分器注册系统
└── Task Queue         # 异步任务队列 (Celery)
```

## 教程：从零到上手（Step-by-step）

### 1/6 环境准备

```bash
# 安装依赖
pip install -e .

# 配置环境变量
export PYTHONPATH=src

# （可选）启动 Redis 作为 Celery broker/back-end
# macOS（Homebrew）
brew install redis && brew services start redis
# Docker 方式
# docker run -d -p 6379:6379 redis:7-alpine
```

### 2/6 准备标准工作区

先看一个最小可运行工作区结构（以分类为例，仓库已提供 `examples/classification`）：

```text
workspace/
├── meta.json
├── input/
│   └── gt.csv
├── output/
│   └── pred.csv
└── logs/
```

你也可以复制仓库内的示例：

```bash
cp -r examples/classification my-cls-workspace
```

### 3/6 基本用法

#### CLI命令行工具

```bash
# 验证工作区
autoscorer validate examples/classification

# 运行模型推理
autoscorer run examples/classification --backend docker

# 执行评分
autoscorer score examples/classification

# 完整流水线 (推理 + 评分)
autoscorer pipeline examples/classification
```

#### Web API服务（可选）

```bash
# 启动API服务器
autoscorer-api
# 或者
uvicorn autoscorer.api.server:app --host 0.0.0.0 --port 8000
```

#### API 使用示例（与 CLI 等价的能力）

```bash
# 查看可用评分器
curl http://localhost:8000/scorers

# 执行完整流水线
curl -X POST http://localhost:8000/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"workspace": "/path/to/workspace"}'

# 仅执行评分
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{"workspace": "/path/to/workspace", "scorer": "classification_f1"}'
```

### 4/6 异步任务（可选）

```bash
# 启动Celery Worker
celery -A celery_app.tasks worker --loglevel=info

# 提交异步任务
autoscorer submit examples/classification --action pipeline

# 监控任务队列 (可选)
celery -A celery_app.tasks flower
```

### 5/6 热加载与自定义评分器（教程）

支持动态注册与热加载评分器，有两种方式：

1) 通过 API 管理

```bash
# 列出当前已注册评分器
curl -s http://localhost:8000/scorers | jq .

# 加载本地 Python 文件中的评分器（将自动扫描 @register 装饰器）
curl -s -X POST http://localhost:8000/scorers/load \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py", "auto_watch": true}' | jq .

# 开启/关闭文件变更监控（热重载）
curl -s -X POST http://localhost:8000/scorers/watch -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py", "check_interval": 1.0}' | jq .
curl -s -X DELETE "http://localhost:8000/scorers/watch?file_path=custom_scorers/my_scorer.py" | jq .

# 测试评分器是否可用
curl -s -X POST http://localhost:8000/scorers/test \
  -H 'Content-Type: application/json' \
  -d '{"scorer_name": "custom_scorer", "workspace": "examples/classification"}' | jq .
```

2) 通过 CLI 管理（注意：CLI 每次为新进程，状态不在进程间保留；热重载建议走 API）

```bash
# 列表
autoscorer scorers list

# 加载并自动开启 watch
autoscorer scorers load --file-path custom_scorers/my_scorer.py

# 重新加载
autoscorer scorers reload --file-path custom_scorers/my_scorer.py

# 测试评分器
autoscorer scorers test --scorer-name custom_scorer --workspace examples/classification
```

自定义评分器模板：

### 内置评分器

| 评分器 | 注册ID | 任务类型 | 描述 |
|--------|--------|----------|------|
| F1-Score | `classification_f1` | 分类 | 宏平均F1分数，适用多类别不均衡数据 |
| Accuracy | `classification_accuracy` | 分类 | 分类准确率，适用类别均衡数据 |
| RMSE | `regression_rmse` | 回归 | 均方根误差，包含MSE、MAE、R²指标 |
| mAP | `detection_map` | 检测 | 平均精度均值，支持IoU阈值配置 |

### 数据格式要求

**分类任务** (`gt.csv` / `pred.csv`):
```csv
id,label
1,cat
2,dog
3,cat
```

**回归任务** (`gt.csv` / `pred.csv`):
```csv
id,value
1,2.5
2,3.8
3,1.2
```

**检测任务** (`gt.json` / `pred.json`):
```json
[
  {
    "image_id": "img_001",
    "bbox": [10, 10, 50, 60],
    "category_id": 1,
    "score": 0.85
  }
]
]
```

### 自定义评分器

```python
from autoscorer.scorers.registry import register
from autoscorer.scorers.base_csv import BaseCSVScorer
from autoscorer.schemas.result import Result

@register("custom_scorer")
class CustomScorer(BaseCSVScorer):
    name = "custom_scorer"
    version = "1.0.0"
    
    def score(self, workspace: Path, params: Dict) -> Result:
        # 实现自定义评分逻辑
        return Result(
            summary={"score": score_value},
            metrics={"custom_metric": score_value},
            # ... 其他字段
        )
```

评分器管理 API 速查：

```bash
# 列出所有评分器
curl http://localhost:8000/scorers

# 加载自定义评分器
curl -X POST http://localhost:8000/scorers/load \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "custom_scorers/my_scorer.py"}'

# 测试评分器
curl -X POST http://localhost:8000/scorers/test \
  -H 'Content-Type: application/json' \
  -d '{"scorer_name": "classification_f1", "workspace": "/path/to/workspace"}'
```

### 6/6 结果与结构（Result 与 Workspace）

每个评分任务需要遵循标准的工作区结构：

```text
workspace/
├── meta.json          # 任务元数据
├── Dockerfile         # 容器构建文件
├── input/             # 输入数据
│   ├── gt.csv         # 标准答案 (分类/回归)
│   ├── gt.json        # 标准答案 (检测)
│   └── data/          # 测试数据
├── output/            # 输出结果
│   ├── pred.csv       # 预测结果 (分类/回归)
│   ├── pred.json      # 预测结果 (检测)
│   └── result.json    # 评分结果
└── logs/              # 执行日志
    ├── container.log  # 容器日志
    └── run_info.json  # 运行信息
```

#### meta.json 配置

```json
{
  "scorer": "classification_f1",
  "params": {
    "threshold": 0.5
  },
  "resources": {
    "cpu": 2,
    "memory": "4Gi",
    "gpu": 0
  },
  "timeout": 300
}
```

## 标准化响应（API/CLI）

API 成功：

```json
{
  "ok": true,
  "data": { /* 具体数据 */ },
  "meta": { "timestamp": "ISO-8601", "version": "0.1.0" }
}
```

API 错误：

```json
{
  "ok": false,
  "error": { "code": "ERROR_CODE", "message": "...", "stage": "...", "details": { } },
  "meta": { "timestamp": "ISO-8601", "version": "0.1.0" }
}
```

CLI 成功：

```json
{ "status": "success", "data": { }, "execution_time": 1.23, "timestamp": "ISO-8601" }
```

CLI 错误：

```json
{ "status": "error", "error": { "code": "...", "message": "...", "stage": "..." }, "timestamp": "ISO-8601" }
```

详见 `docs/OUTPUT_STANDARDS.md`。

## 迁移说明（Breaking changes）

v2 标准化后，以下端点/输出已调整为统一包装：

- `/result`、`/logs`、`/submit`、`/tasks/{id}` 现返回 `{ ok|error, data?, meta }` 结构
- `/scorers/watch` 的 POST/DELETE/GET 统一返回 `make_success_response/make_error_response`

若你的平台依赖旧的裸 JSON，请按新结构解析。

此外，仓库内的临时演示/手动测试脚本已清理或标记弃用（如 `demo_algorithm_standard.py`、`custom_scorers/hot_reload_test*.py`）。
请参考 examples/ 与 tests/，以及 docs/REPO_HYGIENE.md 获取规范。

## 排障与常见问题（FAQ）

1) CLI 已 load 的评分器在 list 时看不到？

- CLI 每次是新进程，注册状态不共享。用 API 方式管理，或在同一进程内验证（例如用 API 的 `/scorers/test`）。

1) score_only/pipeline 的返回结构与旧版本不同？

- 现在 `score_only` 返回 `(Result, Path)`，`pipeline` 返回统一包装的 dict，详见 `pipeline.py` 注释与文档。

1) /logs 或 /result 直接返回文件内容吗？

- 现在封装在成功包装内，字段包含 `path` 与 `content` 或 `result`，请按字段取值。

1) 自定义评分器抛异常如何呈现？

- API/CLI 都会返回标准化错误结构，`error.code/message/stage/details` 可直接用于 UI 呈现与排障。

系统配置集中在 `config.yaml` 中：

```yaml
# 执行器配置
executors:
  docker:
    host: "unix:///var/run/docker.sock"
    timeout: 300
    resources:
      cpu: 2
      memory: "4Gi"
      gpu: 0
  kubernetes:
    enabled: false
    namespace: "autoscorer"

# 任务队列配置
celery:
  broker: "redis://localhost:6379/0"
  backend: "redis://localhost:6379/0"

# 镜像配置
images:
  registry: "docker.io"
  pull_policy: "ifnotpresent"
  
# 安全配置
security:
  allowed_images: []
  resource_limits:
    max_cpu: 8
    max_memory: "16Gi"
```

## 示例任务（Try it now）

### 1. 图像分类 (F1-Score)

```bash
# 运行分类任务
autoscorer pipeline examples/classification

# 查看结果
cat examples/classification/output/result.json
```

### 2. 回归预测 (RMSE)

```bash
# 运行回归任务
autoscorer pipeline examples/regression

# 查看详细指标
cat examples/regression/output/result.json
```

### 3. 目标检测 (mAP)

```bash
# 运行检测任务
autoscorer pipeline examples/detection

# 查看检测结果
cat examples/detection/output/result.json
```

## 错误处理（格式与代码速查）

### 标准化错误格式

所有错误都遵循统一的错误格式：

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "stage": "execution|scoring|validation",
    "details": {
      "workspace": "/path/to/workspace",
      "logs_path": "/path/to/container.log"
    }
  },
  "meta": {
    "timestamp": "2025-09-01T10:00:00Z",
    "version": "2.0.0"
  }
}
```

### 常见错误代码

**执行阶段错误:**

- `IMAGE_NOT_FOUND`: 镜像不存在
- `CONTAINER_FAILED`: 容器执行失败
- `TIMEOUT_ERROR`: 执行超时
- `RESOURCE_ERROR`: 资源不足

**评分阶段错误:**

- `MISSING_FILE`: 缺少必需文件
- `BAD_FORMAT`: 数据格式错误
- `PARSE_ERROR`: 文件解析失败
- `MISMATCH`: 数据不匹配

## 生产部署

### Docker部署

```bash
# 构建镜像
docker build -t autoscorer:latest .

# 运行服务
docker run -d \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/config.yaml:/app/config.yaml \
  autoscorer:latest
```

### Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autoscorer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: autoscorer
  template:
    metadata:
      labels:
        app: autoscorer
    spec:
      containers:
      - name: autoscorer
        image: autoscorer:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
```

### 监控和日志

```bash
# 查看API健康状态
curl http://localhost:8000/healthz

# 查看任务状态
curl http://localhost:8000/tasks/{task_id}

# 查看工作区日志
curl http://localhost:8000/logs?workspace=/path/to/workspace
```

## 开发指南

### 项目结构

```text
src/autoscorer/
├── cli.py              # CLI工具入口
├── pipeline.py         # 核心执行管道
├── scheduler.py        # 任务调度器
├── api/                # Web API
│   ├── server.py       # FastAPI服务器
│   └── run.py          # API路由
├── executor/           # 执行器后端
│   ├── base.py         # 执行器基类
│   ├── docker_executor.py  # Docker执行器
│   └── k8s_executor.py     # K8s执行器
├── scorers/            # 评分器系统
│   ├── registry.py     # 注册系统
│   ├── base_csv.py     # CSV基类
│   ├── classification.py  # 分类评分器
│   ├── regression.py   # 回归评分器
│   └── detection.py    # 检测评分器
├── schemas/            # 数据模型
│   ├── job.py          # 任务模型
│   └── result.py       # 结果模型
└── utils/              # 工具模块
    ├── config.py       # 配置管理
    ├── errors.py       # 错误处理
    └── logger.py       # 日志系统
```

### 开发环境设置

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码格式化
black src/ tests/
isort src/ tests/

# 类型检查
mypy src/
```

## 文档

详细文档请参考 `docs/` 目录：

- [技术设计](docs/TECH_DESIGN.md) - 系统架构和设计理念
- [评分算法](docs/SCORING_ALGORITHMS.md) - 评分器实现详情
- [输入规范](docs/INPUT_SPEC.md) - 数据格式和验证标准
- [输出标准](docs/OUTPUT_STANDARDS.md) - 结果格式规范
- [调度标准](docs/SCHEDULER_STANDARD.md) - 任务调度和资源管理
- [部署指南](docs/DEPLOYMENT.md) - 生产环境部署
- [错误处理](docs/ERROR_HANDLING.md) - 错误机制和排查
- [仓库整洁与测试规范](docs/REPO_HYGIENE.md) - 清理临时脚本与单测规范

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

### 贡献指南

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/new-scorer`)
3. 提交更改 (`git commit -am 'Add new scorer'`)
4. 推送分支 (`git push origin feature/new-scorer`)
5. 创建Pull Request

### 开发规范

- 遵循Python PEP 8代码风格
- 为新功能添加测试用例
- 更新相关文档
- 确保所有测试通过

---

**AutoScorer** - 让ML模型评分更简单、更可靠、更可扩展
