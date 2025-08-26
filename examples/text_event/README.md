# 文本事件智能分析评分器示例

本示例展示如何使用内置评分器 `text_event_analysis` 对生成报告进行自动评分。

- 输入：`input/gt.csv` 包含参考文本列 `reference`
- 输出：`output/pred.csv` 包含生成报告列 `report`
- 评分器：`text_event_analysis`

运行评分（在仓库根目录）：

```**bash**
autoscorer score autoscorer/examples/text_event
```

或使用流水线（示例容器命令只是占位，将直接保留已有的 pred.csv）：

```bash
autoscorer pipeline autoscorer/examples/text_event --backend auto
```

参数可选项（通过 `--params '{"gt_text_col":"reference","pred_text_col":"report"}'` 覆盖）：

- gt_text_col: 参考文本列名（默认 reference）
- pred_text_col: 报告文本列名（默认 report）
- pass_threshold: 通过阈值（默认 0.70）
