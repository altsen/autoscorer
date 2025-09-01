# 工作区规范

本文档详细说明了 AutoScorer 系统的工作区结构和数据格式要求。

## 工作区概述

工作区 (Workspace) 是 AutoScorer 系统的核心概念，它定义了任务执行的标准化环境。每个工作区包含输入数据、输出结果、配置文件和日志等组件。

### 设计原则

- **标准化**: 统一的目录结构和文件格式
- **隔离性**: 每个任务独立的工作环境
- **可复现**: 确保结果可重现和可审计
- **扩展性**: 支持不同类型任务的数据格式

## 目录结构

### 标准工作区结构

```
workspace/
├── meta.json          # 任务配置文件 (必需)
├── input/             # 输入数据目录 (只读)
│   ├── gt.csv         # 标准答案文件
│   ├── data/          # 其他输入数据
│   │   ├── images/    # 图像数据
│   │   ├── texts/     # 文本数据
│   │   └── features/  # 特征数据
│   └── metadata.json  # 输入数据元信息
├── output/            # 输出结果目录 (读写)
│   ├── pred.csv       # 预测结果文件
│   ├── result.json    # 评分结果 (系统生成)
│   └── artifacts/     # 其他输出文件
├── logs/              # 日志目录 (读写)
│   ├── container.log  # 容器执行日志
│   ├── run_info.json  # 运行信息
│   └── debug.log      # 调试日志
├── src/               # 源代码目录 (可选)
│   ├── inference.py   # 推理脚本
│   ├── model/         # 模型文件
│   └── utils/         # 工具函数
├── requirements.txt   # 依赖包 (可选)
└── Dockerfile         # 容器定义 (可选)
```

### 目录权限说明

| 目录 | 权限 | 说明 |
|-----|------|------|
| `input/` | 只读 | 防止意外修改输入数据 |
| `output/` | 读写 | 存储预测结果和评分输出 |
| `logs/` | 读写 | 存储执行日志和调试信息 |
| `src/` | 只读 | 用户代码，容器执行时只读 |

## 配置文件

### meta.json 规范

`meta.json` 是工作区的核心配置文件，定义了任务的执行参数。

#### 基础配置

```json
{
  "job_id": "unique-job-identifier",
  "task_type": "classification",
  "scorer": "classification_f1",
  "version": "1.0",
  "description": "任务描述信息"
}
```

#### 完整配置示例

```json
{
  // 基础信息
  "job_id": "competition-2025-task-001",
  "task_type": "classification", 
  "scorer": "classification_f1",
  "version": "1.0",
  "description": "图像分类竞赛任务",
  
  // 时间和资源限制
  "time_limit": 1800,
  "resources": {
    "cpu": 2.0,
    "memory": "4Gi",
    "gpus": 1,
    "disk": "10Gi"
  },
  
  // 容器配置
  "container": {
    "image": "pytorch/pytorch:1.12.0-cuda11.3-cudnn8-runtime",
    "cmd": ["python", "src/inference.py"],
    "env": {
      "PYTHONUNBUFFERED": "1",
      "CUDA_VISIBLE_DEVICES": "0"
    },
    "working_dir": "/workspace"
  },
  
  // 网络配置
  "network_policy": "restricted",
  
  // 数据配置
  "data": {
    "input_format": "csv",
    "output_format": "csv",
    "encoding": "utf-8",
    "has_header": true
  },
  
  // 评分参数
  "scorer_params": {
    "average": "macro",
    "labels": [0, 1, 2],
    "sample_weight": null
  },
  
  // 标签映射
  "label_mapping": {
    "cat": 0,
    "dog": 1,
    "bird": 2
  }
}
```

#### 字段说明

**基础字段**:
- `job_id`: 全局唯一的任务标识符
- `task_type`: 任务类型 (`classification`, `regression`, `detection`, `segmentation`)
- `scorer`: 评分器名称
- `version`: 配置版本号
- `description`: 任务描述

**资源字段**:
- `time_limit`: 执行时间限制 (秒)
- `resources.cpu`: CPU 核心数 (浮点数)
- `resources.memory`: 内存限制 (如 "4Gi", "512Mi")
- `resources.gpus`: GPU 数量 (整数)
- `resources.disk`: 磁盘空间限制

**容器字段**:
- `container.image`: Docker 镜像名称
- `container.cmd`: 执行命令数组
- `container.env`: 环境变量字典
- `container.working_dir`: 工作目录

**网络字段**:
- `network_policy`: 网络策略 (`none`, `restricted`, `bridge`)

**数据字段**:
- `data.input_format`: 输入格式 (`csv`, `json`, `parquet`)
- `data.output_format`: 输出格式
- `data.encoding`: 文件编码
- `data.has_header`: 是否包含标题行

## 数据格式

### 分类任务

#### 输入数据 (input/gt.csv)

```csv
id,label
1,cat
2,dog  
3,bird
4,cat
5,dog
```

#### 预测结果 (output/pred.csv)

```csv
id,label
1,cat
2,cat
3,bird
4,cat
5,dog
```

#### 概率输出 (可选)

```csv
id,label,prob_cat,prob_dog,prob_bird
1,cat,0.9,0.05,0.05
2,cat,0.7,0.2,0.1
3,bird,0.1,0.1,0.8
4,cat,0.8,0.15,0.05
5,dog,0.2,0.75,0.05
```

### 回归任务

#### 输入数据 (input/gt.csv)

```csv
id,value
1,3.14
2,2.71
3,1.41
4,1.73
5,2.23
```

#### 预测结果 (output/pred.csv)

```csv
id,value
1,3.12
2,2.69
3,1.39
4,1.75
5,2.25
```

### 目标检测任务

#### 输入数据 (input/gt.json)

```json
{
  "images": [
    {
      "id": 1,
      "width": 640,
      "height": 480,
      "file_name": "image001.jpg"
    }
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 1,
      "bbox": [100, 100, 200, 150],
      "area": 30000,
      "iscrowd": 0
    }
  ],
  "categories": [
    {
      "id": 1,
      "name": "person",
      "supercategory": "person"
    }
  ]
}
```

#### 预测结果 (output/pred.json)

```json
[
  {
    "image_id": 1,
    "category_id": 1,
    "bbox": [105, 98, 195, 152],
    "score": 0.95
  }
]
```

### 语义分割任务

#### 输入数据 (input/gt.json)

```json
{
  "images": [
    {
      "id": 1,
      "width": 512,
      "height": 512,
      "file_name": "image001.jpg",
      "mask_file": "mask001.png"
    }
  ],
  "categories": [
    {
      "id": 0,
      "name": "background"
    },
    {
      "id": 1,
      "name": "foreground"
    }
  ]
}
```

#### 预测结果 (output/pred.json)

```json
[
  {
    "image_id": 1,
    "mask_file": "pred_mask001.png"
  }
]
```

## 输出规范

### result.json 结构

评分完成后，系统会在 `output/result.json` 生成标准化的评分结果。

```json
{
  "summary": {
    "score": 0.85,
    "rank": "A",
    "pass": true,
    "message": "评分成功"
  },
  "metrics": {
    "f1_macro": 0.85,
    "accuracy": 0.88,
    "precision": 0.83,
    "recall": 0.87,
    "confusion_matrix": [[45, 5], [8, 42]]
  },
  "artifacts": {
    "confusion_matrix_plot": "artifacts/confusion_matrix.png",
    "roc_curve": "artifacts/roc_curve.png"
  },
  "timing": {
    "total_time": 1.234,
    "scoring_time": 0.045,
    "loading_time": 0.123
  },
  "versioning": {
    "scorer": "classification_f1",
    "version": "2.0.0",
    "timestamp": "2025-09-01T10:00:00Z",
    "autoscorer_version": "2.0.0"
  },
  "metadata": {
    "job_id": "job-001",
    "task_type": "classification",
    "data_size": 1000,
    "num_classes": 3
  }
}
```

### 字段说明

**summary**: 评分摘要
- `score`: 主要得分 (0-1)
- `rank`: 等级评价 (S/A/B/C/D/F)
- `pass`: 是否通过
- `message`: 评分信息

**metrics**: 详细指标
- 具体指标根据评分器类型而定
- 常见指标: accuracy, f1_score, precision, recall, rmse, mae, map

**artifacts**: 输出文件
- 图表、模型、中间结果等文件路径

**timing**: 时间统计
- `total_time`: 总执行时间
- `scoring_time`: 评分计算时间
- `loading_time`: 数据加载时间

**versioning**: 版本信息
- 评分器版本、系统版本、时间戳

**metadata**: 元数据
- 任务信息、数据统计等

## 最佳实践

### 1. 工作区组织

```bash
# 推荐的工作区创建流程
mkdir -p workspace/{input,output,logs,src}

# 设置合适的权限
chmod 755 workspace
chmod -R 644 workspace/input
chmod -R 755 workspace/output workspace/logs
```

### 2. 数据准备

```python
# 数据格式验证示例
import pandas as pd
import json

def validate_classification_data(gt_path, pred_path):
    """验证分类数据格式"""
    gt = pd.read_csv(gt_path)
    pred = pd.read_csv(pred_path)
    
    # 检查必需列
    assert 'id' in gt.columns and 'label' in gt.columns
    assert 'id' in pred.columns and 'label' in pred.columns
    
    # 检查 ID 匹配
    assert set(gt['id']) == set(pred['id'])
    
    # 检查标签类型
    assert gt['label'].dtype == pred['label'].dtype
    
    print("数据格式验证通过")
```

### 3. 配置管理

```python
# 配置文件生成示例
import json

def create_meta_json(job_id, task_type, scorer, **kwargs):
    """生成标准配置文件"""
    meta = {
        "job_id": job_id,
        "task_type": task_type,
        "scorer": scorer,
        "version": "1.0",
        "time_limit": kwargs.get("time_limit", 1800),
        "resources": {
            "cpu": kwargs.get("cpu", 1.0),
            "memory": kwargs.get("memory", "2Gi"),
            "gpus": kwargs.get("gpus", 0)
        }
    }
    
    # 添加容器配置
    if "image" in kwargs:
        meta["container"] = {
            "image": kwargs["image"],
            "cmd": kwargs.get("cmd", ["python", "inference.py"]),
            "env": kwargs.get("env", {})
        }
    
    return meta

# 使用示例
meta = create_meta_json(
    job_id="demo-001",
    task_type="classification",
    scorer="classification_f1",
    image="python:3.10-slim",
    cpu=2.0,
    memory="4Gi"
)

with open("meta.json", "w") as f:
    json.dump(meta, f, indent=2)
```

### 4. 容器化配置

```dockerfile
# 推荐的 Dockerfile 模板
FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /workspace

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/

# 设置执行权限
RUN chmod +x src/inference.py

# 默认命令
CMD ["python", "src/inference.py"]
```

### 5. 错误处理

```python
# 推荐的错误处理模式
import sys
import traceback
import json

def main():
    try:
        # 执行推理逻辑
        result = run_inference()
        
        # 保存结果
        save_predictions(result)
        
        print("推理完成")
        return 0
        
    except Exception as e:
        # 记录错误信息
        error_info = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存错误日志
        with open("logs/error.json", "w") as f:
            json.dump(error_info, f, indent=2)
        
        print(f"执行失败: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

## 验证工具

使用 AutoScorer 提供的验证工具确保工作区符合规范：

```bash
# 验证工作区结构
autoscorer validate /path/to/workspace

# 验证数据格式
autoscorer validate-data /path/to/workspace

# 验证配置文件
autoscorer validate-config /path/to/workspace/meta.json
```

## 常见问题

### Q: 如何处理大文件数据?

A: 推荐使用软链接或挂载的方式：

```bash
# 创建软链接
ln -s /data/large-dataset workspace/input/data

# 或在 Docker 中挂载
docker run -v /data:/workspace/input/data <image>
```

### Q: 如何支持多种数据格式?

A: 在 `meta.json` 中配置数据格式：

```json
{
  "data": {
    "input_format": "parquet",
    "output_format": "json",
    "custom_fields": {
      "image_dir": "input/images",
      "annotation_file": "input/annotations.json"
    }
  }
}
```

### Q: 如何处理中文编码问题?

A: 确保在配置中指定正确的编码：

```json
{
  "data": {
    "encoding": "utf-8",
    "input_encoding": "gbk",
    "output_encoding": "utf-8"
  }
}
```

## 相关文档

- **[评分算法详解](scoring-algorithms.md)** - 了解各种评分器的使用
- **[自定义评分器](custom-scorers.md)** - 开发自己的评分算法
- **[容器化指南](containerization.md)** - 深入了解容器配置
- **[API 参考](api-reference.md)** - 程序化操作工作区
