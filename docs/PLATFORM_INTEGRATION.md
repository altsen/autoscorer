# 平台对接与集成方案

## 1. API 设计

- 任务创建：POST /api/v1/jobs
  - 参数：JobSpec（见 TECH_DESIGN.md）
  - 返回：job_id、状态、队列信息
- 任务状态查询：GET /api/v1/jobs/{job_id}
  - 返回：当前状态、进度、日志摘要
- 结果下载：GET /api/v1/jobs/{job_id}/result
  - 返回：result.json、产物列表、可视化报告
- 日志查询：GET /api/v1/jobs/{job_id}/logs
  - 返回：结构化日志（JSON）、容器 stdout/stderr
- 提交与回调：POST /submit（支持 callback_url 可选字段）
  - 成功回调：`{ ok:true, data:{...}, meta:{ task_id } }`
  - 失败回调：`{ ok:false, error:{ code,message,stage,details }, meta:{ task_id, timestamp, version } }`
  - 去重：相同 workspace 正在运行时，返回 `{ submitted:false, running:true, task_id }`

## 2. 权限与安全

- 任务创建需鉴权（JWT/OAuth2），每个 job 绑定用户/队伍
- 结果与日志仅允许创建者/管理员访问
- 回调 URL 需白名单校验，防止 SSRF；可选回调签名（推荐 HMAC）
- 评分容器禁网、最小权限、只读挂载
- 产物下载需签名/限时 URL

## 3. 任务生命周期与队列

- 任务状态：pending → running → scoring → finished/failed
- 支持优先级队列（如公开榜/私有榜/自测）
- 失败自动重试，最大重试次数可配置；可启用 PRINT_STACKTRACE 打印友好堆栈用于排错
- 任务超时自动终止，资源配额可动态调整

## 4. 结果与报告集成

- 评分结果标准化（result.json），前端可直接渲染 summary/metrics/artifacts
- 支持报告产出（HTML/Markdown/图片），便于前端展示
- 产物归档至对象存储，支持下载与复现

## 5. 对接流程示例

1. 平台前端/后台通过 API 创建评测任务，上传镜像/配置 JobSpec
2. autoscorer worker 拉取任务，执行推理与评分，产出 result.json
3. 平台通过 API 查询状态与结果，或通过 callback_url 接收评分报告
4. 用户可下载评分报告与产物，支持复现与追溯

---

如需对接 FastAPI/Django/Flask 等平台，可直接复用 JobSpec、result.json、队列接口，或通过 CLI/API/worker 进行集成。

### 附：镜像解析与缓存

- 传入的 `container.image` 支持 `repository:tag` 格式，未带 tag 默认解析为 `latest`。
- 执行器将按 `repo:tag` 在本地精确匹配镜像，避免误判拉取；策略由 `IMAGE_PULL_POLICY` 控制。
