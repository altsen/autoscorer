# 评分插件与原理说明

本文档描述当前内置评分器及其评价指标定义、输入输出格式与常见错误。

## 通用输入输出

- 工作区结构：`input/`、`output/`、`meta.json`、`logs/`
- 评分器输出：`result.json`，字段
  - `summary`: 关键指标（简明）
  - `metrics`: 衍生或分项指标
  - `artifacts`: 附件清单（可视化、报告等）
  - `timing/resources/versioning`: 元数据
  - `error`: 标准化错误（可选）

## classification_f1（分类：宏平均 F1）

- 定义：对 gt 中出现的类别取宏平均 F1。
- 数据格式：
  - `input/gt.csv`: `id,label`
  - `output/pred.csv`: `id,label`
- 指标：
  - `summary.f1_macro`
  - `metrics.f1_<label>` 每类 F1
- 适用场景：多分类。可拓展 micro-F1、加权 F1、Top-K。

## classification_acc（分类：准确率）

- 定义：`acc = correct/total`，逐样本精确匹配。
- 数据格式：同上
- 指标：`summary.acc`，`metrics.correct/total`
- 适用场景：单标签分类的基础指标。

## regression_rmse（回归：RMSE）

- 定义：`RMSE = sqrt(mean((y_pred - y_true)^2))`
- 数据格式：
  - `input/gt.csv`: `id,label`（label 为浮点）
  - `output/pred.csv`: `id,label`
- 指标：`summary.rmse`，`metrics.n`
- 适用场景：回归任务，数值越小越好。

## detection_map（目标检测：mAP，预留）

- 原理：参考 COCO/VOC；先匹配，再按 IoU 阈值计算精确率-召回曲线，积分得到 AP，最后对类别取平均。
- 数据格式（建议）：
  - `input/gt.json`: COCO annotations 风格
  - `output/pred.json`: 带 score 的预测框
- 参数：`iou_thresh`、`categories`、`area_range` 等
- 指标：`summary.map`、`map_50`、`map_75`；`metrics.per_class` 等
- 说明：推荐使用 `pycocotools` 实现，当前仓库内为骨架示例。

## 常见错误与排查

- 缺失文件（如 `pred.csv` 不存在）：`error.code = MISSING_FILE`
- CSV 字段缺失（缺 `id` 或 `label`）：`error.code = BAD_FORMAT`
- 数值无法解析：`error.code = PARSE_ERROR`
- 样本对齐失败（pred 多/少样本）：`error.code = MISMATCH`
- 处理超时或资源不足：`error.code = TIMEOUT/OUT_OF_MEMORY`

建议评分器尽量给出清晰的 `details`，如出错样本 id、首个不匹配位置等。
