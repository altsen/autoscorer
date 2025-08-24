# 标准化错误反馈约定（v2.0）

平台在"运行模型（run）"、"评分（score）"和"配置管理"等阶段输出结构化错误，便于前端与调用方统一处理。v2.0版本增强了错误分类、上下文信息和恢复指导。

## 错误对象结构

```json
{
  "ok": false,
  "stage": "validation|execution|scoring|config|scorer_management",
  "code": "STRING_CODE",
  "message": "人类可读的错误描述",
  "details": {
    "context": "具体的上下文信息",
    "suggestions": ["修复建议1", "修复建议2"],
    "related_config": "相关配置项",
    "error_count": 3
  },
  "logs": "/abs/path/to/logs/container.log"
}
```

### 字段说明

- **ok**: 布尔，固定为 false
- **stage**: 错误发生阶段，扩展支持更多场景
- **code**: 机器可读错误码（遵循分层命名约定）
- **message**: 人类可读简要描述
- **details**: 详细上下文信息（新增建议和关联信息）
- **logs**: 可选，相关日志文件路径

## 错误码分类体系

### 1. 配置相关（CONFIG_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `CONFIG_FILE_NOT_FOUND` | 配置文件不存在 | config.yaml缺失 | 创建配置文件或指定正确路径 |
| `CONFIG_PARSE_ERROR` | 配置文件解析失败 | YAML格式错误 | 检查YAML语法 |
| `CONFIG_VALIDATION_ERROR` | 配置验证失败 | 参数值不合法 | 使用`autoscorer config validate`检查 |
| `CONFIG_PERMISSION_ERROR` | 配置文件权限不足 | 文件只读或无访问权限 | 检查文件权限 |

### 2. 工作空间验证（WORKSPACE_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `WORKSPACE_NOT_FOUND` | 工作空间目录不存在 | 路径错误 | 检查workspace路径 |
| `WORKSPACE_PERMISSION_ERROR` | 工作空间权限不足 | 目录不可读写 | 修改目录权限 |
| `MISSING_FILE` | 缺少必要文件 | meta.json或数据文件不存在 | 按标准结构创建文件 |
| `BAD_FORMAT` | 文件格式错误 | CSV/JSON格式不符合要求 | 参考格式规范修正 |

### 3. 容器执行（CONTAINER_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `IMAGE_NOT_PRESENT` | 镜像不存在 | 本地无镜像且策略为never | 拉取镜像或放置image.tar |
| `IMAGE_PULL_FAILED` | 镜像拉取失败 | 网络问题或认证失败 | 检查网络和镜像仓库配置 |
| `CONTAINER_CREATE_FAILED` | 容器创建失败 | 资源不足或参数错误 | 检查资源配置和Docker状态 |
| `CONTAINER_EXIT_NONZERO` | 容器非零退出 | 用户代码错误 | 查看container.log排查代码问题 |
| `TIMEOUT_ERROR` | 执行超时 | 代码运行时间过长 | 优化算法或增加time_limit |

### 4. 评分相关（SCORE_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `SCORER_NOT_FOUND` | 评分器不存在 | meta.json中指定的scorer未注册 | 检查scorer名称或加载自定义scorer |
| `SCORER_LOAD_ERROR` | 评分器加载失败 | Python语法错误或依赖缺失 | 检查scorer代码和依赖 |
| `DATA_VALIDATION_ERROR` | 数据验证失败 | 预测数据格式不正确 | 按照数据格式要求修正输出 |
| `PARSE_ERROR` | 数据解析失败 | 文件编码或格式问题 | 确保UTF-8编码和正确格式 |
| `MISMATCH` | 数据不匹配 | GT和预测的ID不一致 | 确保预测涵盖所有GT样本 |
| `TYPE_ERROR` | 数据类型错误 | 回归任务标签非数值型 | 确保标签为有效数值 |
| `SCORE_ERROR` | 评分计算失败 | 算法计算异常 | 检查数据质量和评分器实现 |

### 5. K8s相关（K8S_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `K8S_CONFIG_ERROR` | K8s配置错误 | API地址或认证信息错误 | 检查K8s配置项 |
| `K8S_CLIENT_ERROR` | K8s客户端错误 | kubernetes库未安装 | 安装kubernetes依赖 |
| `K8S_API_ERROR` | K8s API调用失败 | 权限不足或集群问题 | 检查RBAC权限和集群状态 |
| `K8S_JOB_FAILED` | K8s Job执行失败 | Pod创建或运行失败 | 查看K8s事件和Pod日志 |
| `K8S_JOB_TIMEOUT` | K8s Job超时 | Job运行时间超过限制 | 增加超时时间或优化代码 |

### 6. 评分器管理（SCORER_MGMT_*）

| 错误码 | 描述 | 常见原因 | 修复建议 |
|--------|------|----------|----------|
| `FILE_NOT_FOUND` | scorer文件不存在 | 路径错误 | 检查文件路径 |
| `LOAD_ERROR` | scorer加载失败 | Python语法错误 | 检查代码语法 |
| `RELOAD_ERROR` | scorer重载失败 | 文件被锁定或语法错误 | 释放文件锁定，修正语法 |
| `TEST_ERROR` | scorer测试失败 | 测试数据或逻辑错误 | 检查测试workspace和scorer逻辑 |

## CLI错误输出格式

### 成功响应
```json
{
  "status": "success",
  "data": {
    "result": "操作结果"
  },
  "meta": {
    "timestamp": "2024-01-01T10:00:00Z",
    "execution_time": 1.23,
    "version": "2.0.0"
  }
}
```

### 错误响应
```json
{
  "status": "error",
  "error": {
    "code": "CONTAINER_EXIT_NONZERO",
    "message": "Container exited with code 1",
    "stage": "execution",
    "details": {
      "exit_code": 1,
      "image": "python:3.10-slim",
      "logs_path": "/path/to/logs/container.log",
      "suggestions": [
        "Check container logs for error details",
        "Verify input data format",
        "Ensure all dependencies are installed in the image"
      ]
    }
  },
  "meta": {
    "timestamp": "2024-01-01T10:00:00Z",
    "version": "2.0.0"
  }
}
```

## 前端集成建议

### 1. 错误显示策略

根据错误码显示特定UI和修复建议：

```javascript
function handleError(error) {
  const { code, message, stage, details } = error;
  
  switch (code) {
    case 'CONTAINER_EXIT_NONZERO':
      return showContainerErrorDialog(message, details.logs_path);
    case 'SCORER_NOT_FOUND':
      return showScorerSelectionDialog(details.available_scorers);
    case 'CONFIG_VALIDATION_ERROR':
      return showConfigFixDialog(details.errors);
    default:
      return showGenericErrorDialog(message);
  }
}
```

### 2. 错误预防

- 工作空间上传前的客户端验证
- 配置文件的实时语法检查
- 常见错误的预警提示

这个更新的错误处理文档提供了更全面的错误分类、恢复策略和集成建议，有助于构建更健壮的错误处理机制。准化错误反馈约定

平台在“运行模型（run）”与“评分（score）”两阶段输出结构化错误，便于前端与调用方统一处理。

## 错误对象结构

```json
{
  "ok": false,
  "stage": "run|score",
  "code": "STRING_CODE",
  "message": "人类可读的错误描述",
  "details": {"...": "可选的调试字段"},
  "logs": "/abs/path/to/logs/container.log"
}
```

- ok: 布尔，固定为 false
- stage: 错误发生阶段（run/score）
- code: 机器可读错误码
- message: 人类可读简要描述
- details: 可选，承载上下文，如镜像策略、资源参数、首个出错样本等
- logs: 可选，运行日志路径（便于快速定位）

## 常见错误码

- 运行阶段（run）
  - IMAGE_NOT_PRESENT: 本地无镜像且策略为 never
  - IMAGE_PULL_FAILED: 拉取镜像失败（鉴权/网络）
  - CONTAINER_CREATE_FAILED: 容器创建失败（参数/权限）
  - CONTAINER_WAIT_FAILED: 等待容器退出失败
  - CONTAINER_EXIT_NONZERO: 容器非零退出码
  - EXEC_ERROR: 其他运行阶段异常
- 评分阶段（score）
  - MISSING_FILE: 缺少必要输入/预测文件
  - BAD_FORMAT: 文件格式不符合约定（列缺失/类型错误）
  - PARSE_ERROR: 解析失败（数值异常）
  - MISMATCH: 样本对齐失败
  - SCORE_ERROR: 评分阶段其他异常

## 输出位置

- 运行阶段：CLI 直接打印上述错误对象；日志写入 `logs/container.log`，镜像与执行信息写入 `logs/run_info.json`
- 评分阶段：将包含 `error` 字段的 `result.json` 写入 `output/`，同时在 CLI 打印该对象

## 前端建议

- 依据 `code` 显示针对性文案与引导
- 提供日志下载与“我该如何修复”链接（跳转到 SCORERS.md 相关条目）
- 对可重试的错误（网络/临时异常）提供一键重试

## 运行期调试与回调集成

### 1) 友好堆栈打印开关

- 配置项：`PRINT_STACKTRACE`（布尔，默认 false）。
- 当为 true 时，服务端在捕获未处理异常或任务异常时，使用 rich.traceback 友好打印完整堆栈（回落到标准 traceback 亦可）。
- 适用范围：
  - FastAPI 全局异常处理器
  - Celery 任务的异常分支（run/score/pipeline）

### 2) 异步任务回调

- 提交接口 `/submit` 新增 `callback_url` 可选参数。

- 任务完成（成功）时回调示例：

```json
{ "ok": true, "data": { "pipeline_result": {"...": "..."}, "workspace": "/abs/ws" }, "meta": { "task_id": "<uuid>" } }
```

- 任务失败时回调示例：

```json
{ "ok": false, "error": { "code": "PIPELINE_ERROR", "message": "...", "stage": "pipeline", "details": {"workspace": "/abs/ws"} }, "meta": { "task_id": "<uuid>", "version": "0.1.0", "timestamp": "..." } }
```

### 3) 按 workspace 去重

- `/submit` 会在调度前检查 Celery active 队列，若发现相同 `workspace` 的任务正在运行，则直接返回：

```json
{ "ok": true, "data": { "submitted": false, "running": true, "task_id": "<existing>", "workspace": "/abs/ws" }, "meta": { "action": "submit_dedup" } }
```

- 该策略避免重复占用资源；若确需并发，请调整 workspace 路径或关闭上游并发。
