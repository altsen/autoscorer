# 配置管理

本文档详细说明 AutoScorer 系统的配置管理，包括配置文件结构、环境变量覆盖机制和配置验证。

## 配置架构

AutoScorer 采用简化的配置架构，优先级从高到低为：

1. **环境变量** - 系统环境中的配置变量，最高优先级
2. **配置文件** - YAML 格式的配置文件
3. **默认值** - 代码中的默认值

### 配置文件查找机制

AutoScorer 使用智能配置文件查找机制，按以下顺序搜索配置文件：

1. **指定路径** - 如果提供了绝对路径，直接使用该路径
2. **当前工作目录** - 在当前目录查找 `config.yaml`
3. **项目根目录** - 在 AutoScorer 项目根目录查找 `config.yaml`
4. **用户主目录** - 在 `~/.autoscorer/config.yaml` 查找
5. **系统配置目录** - 在 `/etc/autoscorer/config.yaml` 查找

可以使用以下命令查看配置文件搜索路径：

```bash
autoscorer config paths
```

输出示例：

```json
{
  "status": "success",
  "data": {
    "search_paths": [
      "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml",
      "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml", 
      "/Users/mac/.autoscorer/config.yaml",
      "/etc/autoscorer/config.yaml"
    ],
    "current_config": "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml",
    "search_order": [
      "1. 当前工作目录",
      "2. 项目根目录",
      "3. 用户主目录 (~/.autoscorer/)",
      "4. 系统配置目录 (/etc/autoscorer/)"
    ]
  }
}
```

### 配置文件格式

系统使用 YAML 格式的配置文件，支持环境变量覆盖。

## 主配置文件

### config.yaml 结构

```yaml
# autoscorer 全局配置

# Docker相关配置
DOCKER_HOST: "unix:///var/run/docker.sock"  # 可改为 tcp://host:2375
DOCKER_API_VERSION: "1.43"
DOCKER_TLS_VERIFY: false
DOCKER_CERT_PATH: ""
IMAGE_PULL_POLICY: "ifnotpresent"  # always|ifnotpresent|never

# 资源调度配置
DEFAULT_CPU: 2
DEFAULT_MEMORY: "4g"
DEFAULT_GPU: 0
DEFAULT_SHM_SIZE: "1g"
TIMEOUT: 1800

# 镜像仓库配置
REGISTRY_URL: "registry.example.com"
REGISTRY_USER: ""
REGISTRY_PASS: ""

# 路径配置
WORKSPACE_ROOT: "./examples"
LOG_DIR: "./logs"

# 队列与worker配置
CELERY_BROKER: "redis://localhost:6379/0"
CELERY_BACKEND: "redis://localhost:6379/0"

# 安全配置
SECURITY_OPTS:
  - "no-new-privileges:true"
  - "seccomp=unconfined"

# 资源池配置
NODES:
  - name: "node1"
    host: "tcp://192.168.1.10:2375"
    gpus: 2
    labels: ["gpu", "local"]
  - name: "node2"
    host: "tcp://192.168.1.11:2375"
    gpus: 4
    labels: ["gpu", "cloud"]

# Kubernetes 相关配置
K8S_ENABLED: false
K8S_API: "https://k8s.example.com:6443"
K8S_NAMESPACE: "autoscore"
K8S_TOKEN: ""
K8S_CA_CERT: ""
K8S_DEFAULT_RESOURCES:
  cpu: "2"
  memory: "4Gi"
  gpu: 1
K8S_IMAGE_PULL_SECRET: "registry-secret"
```

## 环境变量覆盖

AutoScorer 支持通过环境变量覆盖配置文件中的任何设置。环境变量的优先级高于配置文件。

### 核心环境变量

```bash
# Docker 配置
export DOCKER_HOST="unix:///var/run/docker.sock"
export DOCKER_API_VERSION="1.43"
export DOCKER_TLS_VERIFY=false
export IMAGE_PULL_POLICY="ifnotpresent"

# 资源配置
export DEFAULT_CPU=2
export DEFAULT_MEMORY="4g"
export DEFAULT_GPU=0
export DEFAULT_SHM_SIZE="1g"
export TIMEOUT=1800

# 镜像仓库配置
export REGISTRY_URL="registry.example.com"
export REGISTRY_USER=""
export REGISTRY_PASS=""

# 路径配置
export WORKSPACE_ROOT="./examples"
export LOG_DIR="./logs"

# Redis/Celery 配置
export CELERY_BROKER="redis://localhost:6379/0"
export CELERY_BACKEND="redis://localhost:6379/0"

# Kubernetes 配置（可选）
export K8S_ENABLED=false
export K8S_API="https://k8s.example.com:6443"
export K8S_NAMESPACE="autoscore"
export K8S_TOKEN=""
export K8S_CA_CERT=""
```

### 类型转换规则

环境变量会根据配置文件中的默认值类型自动转换：

- **布尔值**: `true/1/yes/on` → `True`, 其他 → `False`
- **整数**: 自动转换为 `int`，失败则保持字符串
- **浮点数**: 自动转换为 `float`，失败则保持字符串
- **列表**: 逗号分隔的字符串会转换为列表
- **字符串**: 保持原值

## 配置管理 API

### Config 类

AutoScorer 使用 `Config` 类进行配置管理：

```python
from autoscorer.utils.config import Config, get_config

# 创建配置实例（使用智能查找）
config = Config()  # 自动查找 config.yaml

# 指定配置文件路径
config = Config("path/to/custom-config.yaml")
config = Config("/absolute/path/to/config.yaml")

# 获取全局配置实例（单例）
config = get_config()
```

### 配置文件路径管理

```python
from autoscorer.utils.config import get_config_search_paths, find_config_file

# 获取所有搜索路径
search_paths = get_config_search_paths()
print(search_paths)
# ['/current/dir/config.yaml', '/project/root/config.yaml', 
#  '/home/user/.autoscorer/config.yaml', '/etc/autoscorer/config.yaml']

# 查找第一个存在的配置文件
config_path = find_config_file()
print(config_path)  # '/project/root/config.yaml'

# 获取当前配置实例使用的文件路径
config = Config()
current_path = config.get_config_path()
print(current_path)  # '/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml'
```

### 配置读取

```python
# 基本配置读取（支持环境变量覆盖）
docker_host = config.get("DOCKER_HOST")
cpu_count = config.get("DEFAULT_CPU", 2)  # 默认值为 2

# 嵌套配置读取
k8s_cpu = config.get_nested("K8S_DEFAULT_RESOURCES", "cpu")
node_host = config.get_nested("NODES", 0, "host")  # 第一个节点的主机

# 类型自动转换
enable_k8s = config.get("K8S_ENABLED", False)  # 自动转换布尔值
timeout = config.get("TIMEOUT", 1800)  # 自动转换整数
memory = config.get("DEFAULT_MEMORY", "4g")  # 字符串保持不变
```

### 配置验证

```python
# 验证配置
errors = config.validate()
if errors:
    print("配置错误:")
    for error in errors:
        print(f"  - {error}")
else:
    print("配置验证通过")

# 配置导出（隐藏敏感信息）
config_dump = config.dump()
print(config_dump)
```

### 实际验证规则

当前实现的验证包括：

- **DOCKER_HOST**: 必须以 `unix://` 或 `tcp://` 开头
- **DEFAULT_CPU**: 必须是正数
- **DEFAULT_MEMORY**: 必须符合格式 `\d+(\.\d+)?[gGmM]i?$`（如 `4g`, `2Gi`, `512m`）
- **DEFAULT_GPU**: 必须是非负整数
- **TIMEOUT**: 必须是正整数
- **K8S 配置**: 当 `K8S_ENABLED=true` 时，验证 `K8S_API` 和 `K8S_NAMESPACE`

## CLI 配置管理

### autoscorer config 命令

AutoScorer 提供了 CLI 命令来管理配置：

```bash
# 显示主要配置项
autoscorer config show

# 验证配置文件
autoscorer config validate

# 导出完整配置（隐藏敏感信息）
autoscorer config dump

# 显示配置文件搜索路径
autoscorer config paths

# 使用自定义配置文件
autoscorer config show --config-path /path/to/config.yaml
autoscorer config validate --config-path ./custom-config.yaml
```

### 输出示例

**config show 输出：**

```json
{
  "status": "success",
  "data": {
    "DOCKER_HOST": "unix:///var/run/docker.sock",
    "IMAGE_PULL_POLICY": "ifnotpresent",
    "DEFAULT_CPU": 2,
    "DEFAULT_MEMORY": "4g",
    "DEFAULT_GPU": 0,
    "TIMEOUT": 1800,
    "K8S_ENABLED": false,
    "K8S_NAMESPACE": "autoscore",
    "CELERY_BROKER": "redis://localhost:6379/0",
    "LOG_DIR": "./logs",
    "WORKSPACE_ROOT": "./examples"
  },
  "timestamp": "2025-08-25T03:06:41+00:00",
  "config_file": "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml"
}
```

**config paths 输出：**

```json
{
  "status": "success", 
  "data": {
    "search_paths": [
      "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml",
      "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml",
      "/Users/mac/.autoscorer/config.yaml", 
      "/etc/autoscorer/config.yaml"
    ],
    "current_config": "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml",
    "search_order": [
      "1. 当前工作目录",
      "2. 项目根目录", 
      "3. 用户主目录 (~/.autoscorer/)",
      "4. 系统配置目录 (/etc/autoscorer/)"
    ]
  },
  "timestamp": "2025-08-25T03:30:18+00:00"
}
```

**config validate 成功输出：**

```json
{
  "status": "success",
  "data": {
    "validation": "passed"
  },
  "timestamp": "2025-08-25T03:07:15+00:00",
  "config_file": "/Users/mac/project/sthq/autoscorers/autoscorer/config.yaml"
}
```

**config validate 失败输出：**

```json
{
  "status": "error",
  "error": {
    "code": "CONFIG_VALIDATION_ERROR",
    "message": "Found 2 configuration errors",
    "stage": "config_management",
    "details": {
      "errors": [
        "DOCKER_HOST must start with unix:// or tcp://",
        "DEFAULT_MEMORY invalid format: abc"
      ]
    }
  },
  "timestamp": "2025-08-25T03:07:30+00:00"
}
```

## 部署配置示例

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  autoscorer:
    image: autoscorer:latest
    environment:
      - DOCKER_HOST=unix:///var/run/docker.sock
      - DEFAULT_CPU=4
      - DEFAULT_MEMORY=8g
      - CELERY_BROKER=redis://redis:6379/0
      - WORKSPACE_ROOT=/var/lib/autoscorer/workspaces
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - autoscorer-workspaces:/var/lib/autoscorer/workspaces
      - autoscorer-logs:/var/lib/autoscorer/logs
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  autoscorer-workspaces:
  autoscorer-logs:
  redis-data:
```

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscorer-config
  namespace: autoscorer
data:
  config.yaml: |
    DOCKER_HOST: "tcp://docker-daemon:2375"
    DEFAULT_CPU: 4
    DEFAULT_MEMORY: "8g"
    DEFAULT_GPU: 1
    TIMEOUT: 3600
    
    WORKSPACE_ROOT: "/var/lib/autoscorer/workspaces"
    LOG_DIR: "/var/lib/autoscorer/logs"
    
    CELERY_BROKER: "redis://redis-service:6379/0"
    CELERY_BACKEND: "redis://redis-service:6379/0"
    
    K8S_ENABLED: true
    K8S_NAMESPACE: "autoscorer"

---
apiVersion: v1
kind: Secret
metadata:
  name: autoscorer-secrets
  namespace: autoscorer
type: Opaque
stringData:
  registry-user: "your-registry-user"
  registry-pass: "your-registry-password"
  k8s-token: "your-k8s-token"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autoscorer
  namespace: autoscorer
spec:
  replicas: 2
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
        env:
        - name: REGISTRY_USER
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: registry-user
        - name: REGISTRY_PASS
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: registry-pass
        - name: K8S_TOKEN
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: k8s-token
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: workspace-volume
          mountPath: /var/lib/autoscorer/workspaces
      volumes:
      - name: config-volume
        configMap:
          name: autoscorer-config
      - name: workspace-volume
        persistentVolumeClaim:
          claimName: autoscorer-workspace-pvc
```

## 配置最佳实践

### 1. 安全配置

```yaml
# 生产环境安全配置
REGISTRY_USER: ""  # 通过环境变量设置
REGISTRY_PASS: ""  # 通过环境变量设置
K8S_TOKEN: ""      # 通过环境变量设置

# 安全选项
SECURITY_OPTS:
  - "no-new-privileges:true"
  - "seccomp=unconfined"
  - "apparmor:unconfined"
```

### 2. 性能配置

```yaml
# 高性能环境配置
DEFAULT_CPU: 8
DEFAULT_MEMORY: "16g"
DEFAULT_GPU: 2
DEFAULT_SHM_SIZE: "4g"
TIMEOUT: 7200  # 2小时

# 多节点配置
NODES:
  - name: "gpu-node-1"
    host: "tcp://gpu1.internal:2375"
    gpus: 4
    labels: ["gpu", "high-memory"]
  - name: "gpu-node-2"
    host: "tcp://gpu2.internal:2375"
    gpus: 8
    labels: ["gpu", "ultra-high-memory"]
```

### 3. 开发配置

```yaml
# 开发环境配置
DOCKER_HOST: "unix:///var/run/docker.sock"
DEFAULT_CPU: 1
DEFAULT_MEMORY: "2g"
DEFAULT_GPU: 0
TIMEOUT: 900  # 15分钟

WORKSPACE_ROOT: "./examples"
LOG_DIR: "./logs"

# 使用本地 Redis
CELERY_BROKER: "redis://localhost:6379/0"
CELERY_BACKEND: "redis://localhost:6379/0"

# 禁用 K8s
K8S_ENABLED: false
```

### 4. 监控和日志

```bash
# 环境变量配置
export LOG_LEVEL=INFO
export LOG_FORMAT=json
export METRICS_ENABLED=true
export HEALTH_CHECK_INTERVAL=30
```

## 故障排除

### 常见配置错误

1. **Docker 连接失败**

  ```bash
   # 检查 Docker 守护进程
   docker info
   
   # 检查套接字权限
   ls -la /var/run/docker.sock
   ```

1. **内存格式错误**

  ```yaml
   # 错误格式
   DEFAULT_MEMORY: "4GB"  # ❌
   DEFAULT_MEMORY: "4"    # ❌
   
   # 正确格式
   DEFAULT_MEMORY: "4g"   # ✅
   DEFAULT_MEMORY: "4Gi"  # ✅
   DEFAULT_MEMORY: "4096m" # ✅
   ```

1. **Redis 连接失败**

  ```bash
   # 测试 Redis 连接
   redis-cli -h localhost -p 6379 ping
   
   # 检查配置
   autoscorer config validate
   ```

1. **Kubernetes 配置错误**

  ```bash
   # 检查集群连接
   kubectl cluster-info
   
   # 检查命名空间
   kubectl get ns autoscorer
   
   # 验证配置
   autoscorer config validate
   ```

## 相关文档

- **[CLI 用户指南](cli-guide.md)** - CLI 命令详细说明
- **[API 参考](api-reference.md)** - REST API 接口文档
- **[部署指南](deployment.md)** - 生产环境部署
- **[开发指南](getting-started.md)** - 开发环境搭建
