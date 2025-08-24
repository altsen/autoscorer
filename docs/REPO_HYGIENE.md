# 仓库整洁与测试规范

为保持仓库整洁、稳定、可维护，本项目对临时脚本与测试有如下约定：


## 1. 禁止提交的内容

- 临时验证脚本、一次性 demo、个人调试文件（如：`hot_reload_test*.py`、`demo_*.py`、`scorer_manager.py` 等）
- 运行时生成的产物：`__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`*.log` 等
- 本地虚拟环境文件夹：`.venv/`、`venv/`、`env/`

以上均已通过根目录 `.gitignore` 忽略。

## 2. 测试用例规范

- 统一使用 `pytest`，正式单测放在 `tests/`（或逐步迁移至此）。
- 测试以 API/CLI 合同为准，覆盖：
  - API：健康检查、scorers 列表、score/pipeline 响应结构
  - CLI：validate/run/score/pipeline 正常与错误路径
  - scorers：各内置算法的 happy path + 关键边界

## 3. 热加载与自定义评分器开发

- 通过 API 管理热加载：`/scorers/load`、`/scorers/reload`、`/scorers/watch`、`/scorers/test`
- 不再保留仓库内的临时热加载测试脚本。请使用：
  - `custom_scorers/` 目录存放你自己的评分器实现文件（可被 API 加载）
  - 使用 API 进行加载与测试，避免 CLI 进程状态不共享的问题

## 4. 为什么要清理

- 临时脚本与重复的“手动测试 runner”容易造成项目结构混乱、接口不一致、文档漂移
- 使用统一 API/CLI 与单测可以使行为可预测、易回归、易维护

## 5. 迁移指引

- 原 `custom_scorers/hot_reload_test*.py` 已标注为弃用并将在后续版本移除
- 建议将你的自定义评分器以正式名称放入 `custom_scorers/your_scorer.py`，通过 API 管理热加载
- 需要单测的功能迁移到 `tests/` 下的 `test_*.py`，使用 `pytest`

---
如需更多指导，请查阅：`README.md` 的“热加载与自定义评分器”章节与 `docs/OUTPUT_STANDARDS.md`。

附注：已将根目录下分散的 `test_*.py` 和临时脚本移除/迁移，统一在 `tests/` 目录维护测试。
