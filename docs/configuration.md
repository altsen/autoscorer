# 配置管理

本文档详细说明 AutoScorer 系统的配置管理，包括系统配置、评分器配置、环境变量和配置最佳实践。

## 配置架构

AutoScorer 采用分层配置架构，优先级从高到低为：

1. **命令行参数** - 直接传入的参数，最高优先级
2. **环境变量** - 系统环境中的配置变量
3. **用户配置文件** - 用户目录下的配置文件
4. **项目配置文件** - 项目根目录的 `config.yaml`
5. **默认配置** - 代码中的默认值

### 配置文件格式

系统主要使用 YAML 格式的配置文件，支持层次化配置和环境变量替换。

## 主配置文件

### config.yaml 结构

```yaml
# AutoScorer 主配置文件
# 版本: 2.0.0

# 系统基础配置
system:
  version: "2.0.0"
  environment: "${AUTOSCORER_ENV:development}"  # development, staging, production
  debug: "${AUTOSCORER_DEBUG:false}"
  timezone: "UTC"
  
# 服务器配置
server:
  host: "${AUTOSCORER_HOST:0.0.0.0}"
  port: "${AUTOSCORER_PORT:8000}"
  workers: "${AUTOSCORER_WORKERS:4}"
  max_connections: 1000
  timeout: 300
  cors:
    allow_origins: 
      - "http://localhost:3000"
      - "http://localhost:8080"
    allow_methods: ["GET", "POST", "PUT", "DELETE"]
    allow_headers: ["*"]

# 数据存储配置
storage:
  # 工作区存储
  workspace:
    base_path: "${AUTOSCORER_WORKSPACE_PATH:./workspaces}"
    max_size_mb: 1024
    cleanup_after_days: 30
    
  # 结果存储
  results:
    backend: "${AUTOSCORER_RESULTS_BACKEND:filesystem}"  # filesystem, s3, database
    filesystem:
      path: "${AUTOSCORER_RESULTS_PATH:./results}"
      compression: true
    s3:
      bucket: "${AUTOSCORER_S3_BUCKET:autoscorer-results}"
      region: "${AUTOSCORER_S3_REGION:us-east-1}"
      prefix: "results/"
    database:
      url: "${DATABASE_URL:sqlite:///./autoscorer.db}"
      pool_size: 10
      
  # 日志存储
  logs:
    level: "${AUTOSCORER_LOG_LEVEL:INFO}"
    format: "structured"  # structured, simple
    file: "${AUTOSCORER_LOG_FILE:./logs/autoscorer.log}"
    rotation: "daily"
    retention_days: 30

# Redis 配置 (Celery 消息队列)
redis:
  host: "${REDIS_HOST:localhost}"
  port: "${REDIS_PORT:6379}"
  db: "${REDIS_DB:0}"
  password: "${REDIS_PASSWORD:}"
  max_connections: 50
  socket_timeout: 5
  
# Celery 配置
celery:
  broker_url: "redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}/${REDIS_DB:0}"
  result_backend: "redis://${REDIS_HOST:localhost}:${REDIS_PORT:6379}/${REDIS_DB:1}"
  task_serializer: "json"
  accept_content: ["json"]
  result_serializer: "json"
  timezone: "UTC"
  
  # 任务配置
  task_routes:
    "autoscorer.tasks.score_submission": {"queue": "scoring"}
    "autoscorer.tasks.cleanup_workspace": {"queue": "maintenance"}
  
  # 工作进程配置
  worker:
    concurrency: "${CELERY_WORKERS:4}"
    max_tasks_per_child: 1000
    prefetch_multiplier: 1
    
  # 任务限制
  task_limits:
    time_limit: 1800  # 30 分钟
    soft_time_limit: 1500  # 25 分钟
    
# 执行器配置
executors:
  default: "docker"  # docker, kubernetes, local
  
  # Docker 执行器
  docker:
    enabled: true
    socket_path: "/var/run/docker.sock"
    network: "autoscorer-network"
    cleanup: true
    
    # 资源限制
    resources:
      memory: "2g"
      cpus: "1.0"
      swap: "1g"
      
    # 安全配置
    security:
      read_only: true
      no_new_privileges: true
      user: "1000:1000"
      
    # 镜像配置
    images:
      base: "autoscorer/base:latest"
      python: "autoscorer/python:3.10"
      
  # Kubernetes 执行器
  kubernetes:
    enabled: false
    config_file: "${KUBECONFIG:~/.kube/config}"
    namespace: "${K8S_NAMESPACE:autoscorer}"
    
    # 资源配置
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"
        
    # Pod 配置
    pod_template:
      security_context:
        run_as_non_root: true
        run_as_user: 1000
      
# 评分器配置
scorers:
  # 注册表配置
  registry:
    auto_discover: true
    watch_directories:
      - "./custom_scorers"
      - "./src/autoscorer/scorers/builtin"
    hot_reload: "${AUTOSCORER_HOT_RELOAD:true}"
    check_interval: 2.0
    
  # 默认参数
  defaults:
    timeout: 300
    memory_limit: "1g"
    
  # 内置评分器配置
  builtin:
    classification:
      default_params:
        average: "macro"
        zero_division: 0
    regression:
      default_params:
        metrics: ["rmse", "mae", "r2"]
    detection:
      default_params:
        iou_threshold: 0.5
        confidence_threshold: 0.5

# 安全配置
security:
  # API 认证
  authentication:
    enabled: "${AUTOSCORER_AUTH_ENABLED:false}"
    method: "jwt"  # jwt, api_key, oauth2
    
  # JWT 配置
  jwt:
    secret_key: "${JWT_SECRET_KEY:your-secret-key-here}"
    algorithm: "HS256"
    expiration_hours: 24
    
  # API 密钥配置
  api_key:
    header_name: "X-API-Key"
    valid_keys:
      - "${AUTOSCORER_API_KEY:development-key}"
      
  # 速率限制
  rate_limit:
    enabled: true
    requests_per_minute: 60
    burst_size: 10
    
  # 输入验证
  validation:
    max_file_size_mb: 100
    allowed_extensions: [".csv", ".json", ".txt", ".jpg", ".png"]
    scan_uploads: false

# 监控配置
monitoring:
  # 健康检查
  health_check:
    enabled: true
    interval: 30
    timeout: 10
    
  # 指标收集
  metrics:
    enabled: "${AUTOSCORER_METRICS_ENABLED:false}"
    endpoint: "/metrics"
    include_system: true
    
  # 追踪配置
  tracing:
    enabled: "${AUTOSCORER_TRACING_ENABLED:false}"
    service_name: "autoscorer"
    
# 开发配置
development:
  reload: true
  debug_toolbar: true
  test_data_path: "./tests/data"
  
# 生产配置
production:
  reload: false
  debug_toolbar: false
  compress_responses: true
  cache_static: true
```

## 环境变量

### 必需环境变量

```bash
# 基础配置
export AUTOSCORER_ENV=production
export AUTOSCORER_HOST=0.0.0.0
export AUTOSCORER_PORT=8000

# Redis 连接
export REDIS_HOST=redis.example.com
export REDIS_PORT=6379
export REDIS_PASSWORD=your-redis-password

# 安全配置
export JWT_SECRET_KEY=your-super-secret-jwt-key
export AUTOSCORER_API_KEY=your-api-key

# 存储配置
export AUTOSCORER_WORKSPACE_PATH=/var/lib/autoscorer/workspaces
export AUTOSCORER_RESULTS_PATH=/var/lib/autoscorer/results
```

### 可选环境变量

```bash
# 调试和日志
export AUTOSCORER_DEBUG=false
export AUTOSCORER_LOG_LEVEL=INFO
export AUTOSCORER_LOG_FILE=/var/log/autoscorer.log

# 性能配置
export AUTOSCORER_WORKERS=4
export CELERY_WORKERS=8
export REDIS_MAX_CONNECTIONS=100

# 功能开关
export AUTOSCORER_AUTH_ENABLED=true
export AUTOSCORER_HOT_RELOAD=false
export AUTOSCORER_METRICS_ENABLED=true

# 存储后端
export AUTOSCORER_RESULTS_BACKEND=s3
export AUTOSCORER_S3_BUCKET=my-autoscorer-bucket
export AUTOSCORER_S3_REGION=us-west-2

# 数据库连接 (如果使用数据库后端)
export DATABASE_URL=postgresql://user:pass@localhost/autoscorer

# Kubernetes 配置
export K8S_NAMESPACE=autoscorer-prod
export KUBECONFIG=/etc/kubernetes/admin.conf
```

## 评分器配置

### 全局评分器配置

```yaml
# scorer_config.yaml
scorers:
  # 全局默认配置
  global_defaults:
    timeout: 300
    memory_limit: "1g"
    enable_artifacts: true
    precision: 4
    
  # 按类型配置
  by_task_type:
    classification:
      default_average: "macro"
      pass_threshold: 0.6
      rank_thresholds:
        S: 0.95
        A: 0.9
        B: 0.8
        C: 0.7
        D: 0.6
        
    regression:
      primary_metric: "rmse"
      pass_threshold: 0.5  # R² score
      normalize_metrics: true
      
    detection:
      iou_thresholds: [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
      area_ranges:
        - [0, 1024]      # small
        - [1024, 9216]   # medium  
        - [9216, null]   # large
      max_detections: [1, 10, 100]
      
  # 特定评分器配置
  by_scorer:
    enhanced_classification:
      version: "1.2.0"
      config:
        support_probability: true
        class_weights_auto: true
        confusion_matrix: true
        
    advanced_regression:
      version: "1.1.0"
      config:
        robust_statistics: true
        outlier_detection: true
        residual_analysis: true
        
    object_detection_map:
      version: "1.0.0"
      config:
        coco_format: true
        interpolation_points: 101
        area_analysis: true
```

### 评分器特定配置

每个评分器可以有自己的配置文件：

```yaml
# custom_scorers/configs/my_scorer_config.yaml
name: "my_custom_scorer"
version: "1.0.0"

# 参数定义
parameters:
  threshold:
    type: "float"
    default: 0.5
    min: 0.0
    max: 1.0
    description: "Decision threshold for binary classification"
    
  average_method:
    type: "string" 
    default: "macro"
    choices: ["macro", "micro", "weighted", "binary"]
    description: "Averaging strategy for multi-class metrics"
    
  class_weights:
    type: "object"
    default: null
    description: "Custom weights for each class"
    
# 输出配置
output:
  precision: 4
  include_confusion_matrix: true
  save_artifacts: true
  
# 性能配置
performance:
  timeout: 180
  memory_limit: "512m"
  parallel: false
  
# 验证规则
validation:
  required_files: ["gt.csv", "pred.csv"]
  required_columns:
    gt.csv: ["id", "label"] 
    pred.csv: ["id", "label"]
  data_types:
    id: ["string", "int"]
    label: ["string", "int", "float"]
```

## 配置管理 API

### 配置读取

```python
from autoscorer.config import get_config, get_scorer_config

# 获取系统配置
config = get_config()
redis_host = config.redis.host
server_port = config.server.port

# 获取评分器配置
scorer_config = get_scorer_config("my_custom_scorer")
threshold = scorer_config.parameters.threshold.default
```

### 配置验证

```python
from autoscorer.config.validator import validate_config
from autoscorer.utils.errors import ConfigurationError

def validate_system_config(config_dict: Dict[str, Any]) -> None:
    """验证系统配置"""
    try:
        # 验证必需字段
        required_fields = ["system.version", "redis.host", "storage.workspace.base_path"]
        for field in required_fields:
            if not _get_nested_value(config_dict, field):
                raise ConfigurationError(
                    code="MISSING_CONFIG",
                    message=f"Required configuration field missing: {field}"
                )
        
        # 验证数值范围
        if config_dict.get("server", {}).get("port", 0) < 1024:
            raise ConfigurationError(
                code="INVALID_CONFIG", 
                message="Server port must be >= 1024"
            )
            
        # 验证目录权限
        workspace_path = Path(config_dict["storage"]["workspace"]["base_path"])
        if not workspace_path.exists():
            workspace_path.mkdir(parents=True, exist_ok=True)
            
        if not os.access(workspace_path, os.W_OK):
            raise ConfigurationError(
                code="PERMISSION_ERROR",
                message=f"Workspace directory not writable: {workspace_path}"
            )
            
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        else:
            raise ConfigurationError(
                code="CONFIG_VALIDATION_ERROR",
                message=f"Configuration validation failed: {str(e)}"
            )

def _get_nested_value(data: Dict, key_path: str) -> Any:
    """获取嵌套字典值"""
    keys = key_path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value
```

### 动态配置更新

```python
from autoscorer.config.manager import ConfigManager

class DynamicConfigManager:
    """动态配置管理器"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.watchers = []
        
    def watch_config_file(self, file_path: str, callback: callable):
        """监控配置文件变化"""
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        
        class ConfigFileHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.src_path == file_path:
                    callback(file_path)
        
        observer = Observer()
        observer.schedule(ConfigFileHandler(), Path(file_path).parent, recursive=False)
        observer.start()
        self.watchers.append(observer)
        
    def reload_config(self, file_path: str):
        """重新加载配置文件"""
        try:
            new_config = self.config_manager.load_config(file_path)
            self.config_manager.validate_config(new_config)
            self.config_manager.update_config(new_config)
            
            logger.info(f"Configuration reloaded from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            
    def get_effective_config(self) -> Dict[str, Any]:
        """获取当前有效配置"""
        return self.config_manager.get_merged_config()
```

## 部署配置

### Docker 环境配置

```yaml
# docker-compose.yaml
version: '3.8'

services:
  autoscorer:
    image: autoscorer:latest
    environment:
      - AUTOSCORER_ENV=production
      - REDIS_HOST=redis
      - DATABASE_URL=postgresql://user:pass@postgres:5432/autoscorer
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - autoscorer-workspaces:/var/lib/autoscorer/workspaces
      - autoscorer-results:/var/lib/autoscorer/results
    depends_on:
      - redis
      - postgres
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
      
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=autoscorer
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  autoscorer-workspaces:
  autoscorer-results:
  redis-data:
  postgres-data:
```

### Kubernetes 配置

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscorer-config
data:
  config.yaml: |
    system:
      environment: production
    server:
      host: 0.0.0.0
      port: 8000
    redis:
      host: redis-service
      port: 6379
    storage:
      workspace:
        base_path: /var/lib/autoscorer/workspaces
      results:
        backend: s3
        s3:
          bucket: autoscorer-prod-results
          region: us-west-2

---
apiVersion: v1
kind: Secret
metadata:
  name: autoscorer-secrets
type: Opaque
stringData:
  jwt-secret: your-super-secret-jwt-key
  api-key: your-production-api-key
  redis-password: your-redis-password

---
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
        - name: AUTOSCORER_ENV
          value: "production"
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: jwt-secret
        - name: AUTOSCORER_API_KEY
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: api-key
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: redis-password
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
# 生产环境安全配置示例
security:
  # 使用强密钥
  jwt:
    secret_key: "${JWT_SECRET_KEY}"  # 从环境变量读取
    algorithm: "RS256"  # 使用 RSA 算法
    
  # 启用认证
  authentication:
    enabled: true
    method: "jwt"
    
  # 配置 HTTPS
  ssl:
    enabled: true
    cert_file: "/etc/ssl/certs/autoscorer.crt"
    key_file: "/etc/ssl/private/autoscorer.key"
    
  # 输入验证
  validation:
    max_file_size_mb: 50
    scan_uploads: true
    allowed_extensions: [".csv", ".json"]
```

### 2. 性能配置

```yaml
# 高性能配置示例
performance:
  # 连接池配置
  redis:
    max_connections: 100
    connection_pool_kwargs:
      max_connections: 100
      retry_on_timeout: true
      
  # 数据库连接池
  database:
    pool_size: 20
    max_overflow: 30
    pool_timeout: 30
    
  # 缓存配置
  cache:
    enabled: true
    backend: "redis"
    default_timeout: 300
    key_prefix: "autoscorer:"
    
  # 任务队列配置
  celery:
    worker:
      concurrency: 8
      prefetch_multiplier: 1
      max_tasks_per_child: 1000
```

### 3. 监控配置

```yaml
# 监控和观测性配置
monitoring:
  # 日志配置
  logging:
    level: "INFO"
    format: "json"
    fields:
      - timestamp
      - level
      - message
      - request_id
      - user_id
      
  # 指标收集
  metrics:
    enabled: true
    collectors:
      - system
      - application
      - business
    export:
      prometheus:
        enabled: true
        endpoint: "/metrics"
        
  # 分布式追踪
  tracing:
    enabled: true
    service_name: "autoscorer"
    sampler_type: "probabilistic"
    sampler_param: 0.1
    
  # 健康检查
  health:
    endpoint: "/health"
    checks:
      - database
      - redis
      - filesystem
```

### 4. 开发配置

```yaml
# 开发环境配置
development:
  # 热重载
  reload: true
  
  # 调试工具
  debug:
    enabled: true
    toolbar: true
    profiler: true
    
  # 测试数据
  test_data:
    auto_generate: true
    cleanup: true
    
  # Mock 服务
  mocks:
    external_apis: true
    slow_operations: false
```

## 配置命令行工具

### 配置验证工具

```bash
# 验证配置文件
python -m autoscorer.config validate config.yaml

# 检查环境变量
python -m autoscorer.config check-env

# 生成默认配置
python -m autoscorer.config generate --template production

# 配置文档生成
python -m autoscorer.config docs --output config-docs.md
```

### 配置管理脚本

```python
#!/usr/bin/env python3
"""
配置管理命令行工具
"""

import click
import yaml
from pathlib import Path
from autoscorer.config import validate_config, generate_default_config

@click.group()
def config_cli():
    """AutoScorer 配置管理工具"""
    pass

@config_cli.command()
@click.argument('config_file', type=click.Path(exists=True))
def validate(config_file):
    """验证配置文件"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        validate_config(config)
        click.echo(f"✓ 配置文件 {config_file} 验证通过")
        
    except Exception as e:
        click.echo(f"✗ 配置验证失败: {e}", err=True)
        exit(1)

@config_cli.command()
@click.option('--template', type=click.Choice(['development', 'production']))
@click.option('--output', default='config.yaml')
def generate(template, output):
    """生成默认配置文件"""
    config = generate_default_config(template)
    
    with open(output, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    click.echo(f"配置文件已生成: {output}")

if __name__ == '__main__':
    config_cli()
```

## 相关文档

- **[部署指南](deployment.md)** - 生产部署配置
- **[API 参考](api-reference.md)** - 配置 API 接口  
- **[开发指南](development.md)** - 开发环境配置
- **[错误处理](error-handling.md)** - 配置错误诊断
- **[安全配置](../security/README.md)** - 安全相关配置
