# 部署指南

本指南严格依据仓库现状，提供可复制的部署方式，并指向真实可用的端点与服务。

- API 服务启动：`python -m autoscorer.api.run`（或 `autoscorer-api`）
- 健康检查端点：`GET /healthz`
- Celery 任务模块：`celery_app.tasks`
- 配置文件：`config.yaml`（自动搜索：CWD → 项目根 → ~/.autoscorer → /etc/autoscorer；可用 `--config-path` 指定）

## 一键启动（推荐）

已提供 Makefile 与 Compose，适合本地与 PoC：

```bash
# 构建并启动所有服务（api, worker, redis, flower）
make up

# 查看服务状态与日志
make ps
make logs

# 打开 Flower 监控（http://localhost:5555）
make flower

# 停止并清理
make down
```

说明：Makefile 内置 DOCKER_BUILDKIT=0，避免在受限网络环境下的 BuildKit 前端拉取失败。

## 构建镜像

仓库提供 `Dockerfile`，默认工作目录 `/app`。

```bash
# 构建本地镜像
docker build -t autoscorer:local .
```

要点：

- 已设置 `PYTHONPATH=/app/src` 便于导入包。
- 若网络对 BuildKit 前端有限制，可用 `DOCKER_BUILDKIT=0 docker build ...`（Makefile 已内置）。

## 单容器运行（仅 API）

```bash
# 运行 API（如果使用 Docker 执行器，需挂载宿主 docker.sock）
docker run -d \
  --name autoscorer_api \
  -p 8000:8000 \
  -e DOCKER_HOST=unix:///var/run/docker.sock \
  -e IMAGE_PULL_POLICY=ifnotpresent \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  autoscorer:local

# 健康检查
curl -s http://localhost:8000/healthz | jq .
```

说明：

- 不使用 Docker 执行器时，可不挂载 `/var/run/docker.sock`。

## Docker Compose（API + Redis + Worker + Flower）

`docker-compose.yml` 已与实现对齐：

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"

  api:
    build: .
    image: autoscorer:local
    container_name: autoscorer_api
    depends_on:
      - redis
    environment:
      - PYTHONPATH=src
      - CELERY_BROKER=redis://redis:6379/0
      - CELERY_BACKEND=redis://redis:6379/0
      - IMAGE_PULL_POLICY=ifnotpresent
      # 如需连接宿主 Docker，请使用以下 DOCKER_HOST（macOS/Windows 使用不同映射方案）
      - DOCKER_HOST=unix:///var/run/docker.sock
      # 路径映射：容器路径 -> 宿主路径，用于 docker.sock 挂载场景下将卷映射回宿主
      - CONTAINER_PROJECT_ROOT=/app
      - HOST_PROJECT_ROOT=${PWD}
      - CONTAINER_EXAMPLES_ROOT=/data/examples
      - HOST_EXAMPLES_ROOT=${PWD}/examples
    volumes:
      - ./:/app
      - /var/run/docker.sock:/var/run/docker.sock
      - ./examples:/data/examples
      - ./config.yaml:/app/config.yaml:ro
    working_dir: /app
    ports:
      - "8000:8000"
    command: ["python", "-m", "autoscorer.api.run"]
    restart: unless-stopped

  worker:
    build: .
    image: autoscorer:local
    container_name: autoscorer_worker
    depends_on:
      - redis
      - api
    environment:
      - PYTHONPATH=src
      - CELERY_BROKER=redis://redis:6379/0
      - CELERY_BACKEND=redis://redis:6379/0
      - DOCKER_HOST=unix:///var/run/docker.sock
      - CONTAINER_PROJECT_ROOT=/app
      - HOST_PROJECT_ROOT=${PWD}
      - CONTAINER_EXAMPLES_ROOT=/data/examples
      - HOST_EXAMPLES_ROOT=${PWD}/examples
    volumes:
      - ./:/app
      - /var/run/docker.sock:/var/run/docker.sock
      - ./examples:/data/examples
      - ./config.yaml:/app/config.yaml:ro
    working_dir: /app
    command: ["bash", "-lc", "celery -A celery_app.tasks worker --loglevel=info"]
    restart: unless-stopped

  flower:
    image: mher/flower:latest
    container_name: autoscorer_flower
    depends_on:
      - redis
    command: [
      "celery",
      "flower",
      "--broker=redis://redis:6379/0",
      "--result-backend=redis://redis:6379/0",
      "--address=0.0.0.0",
      "--port=5555"
    ]
    ports:
      - "5555:5555"
    restart: unless-stopped
```

启动与验证：

```bash
# 启动（包含构建，等价于 make up）
docker compose up -d --build

# 健康检查
curl -s http://localhost:8000/healthz | jq .

# 列出评分器
curl -s http://localhost:8000/scorers | jq .

# Flower 监控
open http://localhost:5555  # macOS
```

提交任务：

```bash
# 同步调用（流水线）
curl -s -X POST http://localhost:8000/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"workspace":"/app/examples/classification"}' | jq .

# 异步（Celery）
autoscorer submit examples/classification --action pipeline
```

### macOS/Windows 注意事项（docker.sock 与路径共享）

当以 docker.sock 模式连接宿主 Docker 时，容器内路径需要映射回宿主路径供子容器挂载：

- 在 compose 中已设置以下环境变量，由执行器自动完成映射：
  - CONTAINER_PROJECT_ROOT=/app → HOST_PROJECT_ROOT=${PWD}
  - CONTAINER_EXAMPLES_ROOT=/data/examples → HOST_EXAMPLES_ROOT=${PWD}/examples
- 在 Docker Desktop 中开启“File Sharing”，确保工程目录、examples 目录被共享，否则会出现 “Mounts denied” 错误。
- 若 ${PWD} 未被正确展开，请在命令前导出：`export PWD=$PWD`，或将上面 HOST_* 路径替换为绝对路径。

## 容器内配置管理

配置搜索顺序：CWD → 项目根 `/app` → `~/.autoscorer` → `/etc/autoscorer`。

```bash
# 查看搜索路径与当前命中
docker compose exec api autoscorer config paths | jq .
```

常用环境变量覆盖：

- `DOCKER_HOST`、`IMAGE_PULL_POLICY`
- `DEFAULT_CPU`、`DEFAULT_MEMORY`、`DEFAULT_GPU`、`TIMEOUT`

## Kubernetes 最小化提示

- 镜像推送到你的仓库，例如 `registry.example.com/autoscorer:latest`。
- Deployment 容器命令：`python -m autoscorer.api.run`，容器端口 8000。
- 探针示例：

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 20
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

如需在 K8s 内使用容器执行，建议采用 K8s 执行器；若必须使用 Docker 执行器，需确保合规访问底层运行时（不建议直接暴露 docker.sock）。

## 常见问题

- 健康检查 404：使用 `/healthz`。
- 镜像拉取失败：检查 `IMAGE_PULL_POLICY` 与镜像可用性，或在工作区放置 `image.tar`。
- Worker 连接失败：确认 `CELERY_BROKER`/`CELERY_BACKEND` 与网络连通。
- Docker 权限问题：检查 `/var/run/docker.sock` 挂载与容器用户权限。

## 开发环境速启

```bash
pip install -e .
autoscorer-api
PYTHONPATH=src celery -A celery_app.tasks worker --loglevel=info
```


## Kubernetes 部署

### 命名空间和配置

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: autoscorer
  labels:
    name: autoscorer

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscorer-config
  namespace: autoscorer
data:
  config.yaml: |
    system:
      environment: production
      debug: false
      
    server:
      host: 0.0.0.0
      port: 8000
      workers: 4
      
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
          
    executors:
      default: kubernetes
      kubernetes:
        enabled: true
        namespace: autoscorer
        
    security:
      authentication:
        enabled: true
        method: jwt
      rate_limit:
        enabled: true
        requests_per_minute: 60

---
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: autoscorer-secrets
  namespace: autoscorer
type: Opaque
stringData:
  jwt-secret: your-super-secret-jwt-key
  api-key: your-production-api-key
  redis-password: your-redis-password
  aws-access-key-id: your-aws-access-key
  aws-secret-access-key: your-aws-secret-key
```

### 存储配置

```yaml
# k8s/storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: autoscorer-workspace-pvc
  namespace: autoscorer
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: autoscorer-results-pvc
  namespace: autoscorer
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500Gi
  storageClassName: standard
```

### Redis 部署

```yaml
# k8s/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: autoscorer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
          - redis-server
          - --requirepass
          - $(REDIS_PASSWORD)
        ports:
        - containerPort: 6379
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: redis-password
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: 512Mi
            cpu: 250m
          limits:
            memory: 1Gi
            cpu: 500m
        livenessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: autoscorer
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: autoscorer
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### AutoScorer 主服务

```yaml
# k8s/autoscorer.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autoscorer
  namespace: autoscorer
  labels:
    app: autoscorer
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: autoscorer
      component: api
  template:
    metadata:
      labels:
        app: autoscorer
        component: api
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: autoscorer
        image: autoscorer:latest
        ports:
        - containerPort: 8000
        env:
        - name: AUTOSCORER_ENV
          value: production
        - name: REDIS_HOST
          value: redis-service
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: redis-password
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
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: aws-access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: aws-secret-access-key
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: workspace-volume
          mountPath: /var/lib/autoscorer/workspaces
        resources:
          requests:
            memory: 1Gi
            cpu: 500m
          limits:
            memory: 2Gi
            cpu: 1000m
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
      volumes:
      - name: config-volume
        configMap:
          name: autoscorer-config
      - name: workspace-volume
        persistentVolumeClaim:
          claimName: autoscorer-workspace-pvc
      serviceAccountName: autoscorer-service-account

---
apiVersion: v1
kind: Service
metadata:
  name: autoscorer-service
  namespace: autoscorer
spec:
  selector:
    app: autoscorer
    component: api
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: autoscorer-service-account
  namespace: autoscorer

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: autoscorer-cluster-role
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["create", "delete", "get", "list", "watch"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "delete", "get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: autoscorer-cluster-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: autoscorer-cluster-role
subjects:
- kind: ServiceAccount
  name: autoscorer-service-account
  namespace: autoscorer
```

### Celery Worker

```yaml
# k8s/worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autoscorer-worker
  namespace: autoscorer
  labels:
    app: autoscorer
    component: worker
spec:
  replicas: 5
  selector:
    matchLabels:
      app: autoscorer
      component: worker
  template:
    metadata:
      labels:
        app: autoscorer
        component: worker
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: worker
        image: autoscorer:latest
        command: ["celery", "-A", "autoscorer.celery_app.worker", "worker", "--loglevel=info"]
        env:
        - name: AUTOSCORER_ENV
          value: production
        - name: REDIS_HOST
          value: redis-service
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: autoscorer-secrets
              key: redis-password
        - name: CELERY_WORKERS
          value: "4"
        volumeMounts:
        - name: config-volume
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: workspace-volume
          mountPath: /var/lib/autoscorer/workspaces
        resources:
          requests:
            memory: 2Gi
            cpu: 1000m
          limits:
            memory: 4Gi
            cpu: 2000m
        livenessProbe:
          exec:
            command:
            - celery
            - -A
            - autoscorer.celery_app.worker
            - status
          initialDelaySeconds: 60
          periodSeconds: 30
      volumes:
      - name: config-volume
        configMap:
          name: autoscorer-config
      - name: workspace-volume
        persistentVolumeClaim:
          claimName: autoscorer-workspace-pvc
      serviceAccountName: autoscorer-service-account
```

### Ingress 配置

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: autoscorer-ingress
  namespace: autoscorer
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/rate-limit: "60"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - autoscorer.yourdomain.com
    secretName: autoscorer-tls
  rules:
  - host: autoscorer.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: autoscorer-service
            port:
              number: 80
```

## 云服务部署

### AWS EKS 部署

```bash
#!/bin/bash
# deploy-aws-eks.sh

set -e

# 配置变量
CLUSTER_NAME="autoscorer-prod"
REGION="us-west-2"
NODE_GROUP_NAME="autoscorer-nodes"

echo "Creating EKS cluster..."
eksctl create cluster \
  --name $CLUSTER_NAME \
  --region $REGION \
  --nodegroup-name $NODE_GROUP_NAME \
  --node-type m5.large \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 10 \
  --ssh-access \
  --ssh-public-key ~/.ssh/id_rsa.pub \
  --managed

echo "Installing AWS Load Balancer Controller..."
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller//crds?ref=master"

helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

echo "Installing cert-manager..."
kubectl apply -f https://github.com/jetstack/cert-manager/releases/download/v1.8.0/cert-manager.yaml

echo "Creating AutoScorer namespace and resources..."
kubectl apply -f k8s/

echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/autoscorer -n autoscorer

echo "Getting LoadBalancer URL..."
kubectl get ingress autoscorer-ingress -n autoscorer
```

## 监控和日志

### Prometheus 监控

```yaml
# monitoring/prometheus.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: autoscorer
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    rule_files:
      - "autoscorer_rules.yml"

    scrape_configs:
      - job_name: 'autoscorer'
        static_configs:
          - targets: ['autoscorer-service:80']
        scrape_interval: 5s
        metrics_path: /metrics

      - job_name: 'redis'
        static_configs:
          - targets: ['redis-service:6379']

      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
        - role: pod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: autoscorer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config-volume
          mountPath: /etc/prometheus
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus/'
          - '--web.console.libraries=/etc/prometheus/console_libraries'
          - '--web.console.templates=/etc/prometheus/consoles'
          - '--web.enable-lifecycle'
      volumes:
      - name: config-volume
        configMap:
          name: prometheus-config

---
apiVersion: v1
kind: Service
metadata:
  name: prometheus-service
  namespace: autoscorer
spec:
  selector:
    app: prometheus
  ports:
  - port: 9090
    targetPort: 9090
```

## 部署脚本

### 自动化部署脚本（示例，已改为 docker compose 与 /healthz）

```bash
#!/bin/bash
# deploy.sh - AutoScorer 自动化部署脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    
  # Docker Compose V2（docker compose）随 Docker Desktop 提供
  if ! docker compose version &> /dev/null; then
    log_error "Docker Compose V2 not found. Please install/update Docker."
    exit 1
  fi
    
    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl not found. Kubernetes deployment will not be available."
    fi
    
    log_info "Dependencies check completed."
}

# 生成配置文件
generate_config() {
    log_info "Generating configuration files..."
    
    if [[ ! -f .env ]]; then
        log_info "Creating .env file..."
        cat > .env << EOF
# AutoScorer Environment Configuration
JWT_SECRET_KEY=$(openssl rand -hex 32)
AUTOSCORER_API_KEY=$(openssl rand -hex 16)
REDIS_PASSWORD=$(openssl rand -hex 16)
POSTGRES_USER=autoscorer
POSTGRES_PASSWORD=$(openssl rand -hex 16)
FLOWER_BASIC_AUTH=admin:$(openssl rand -hex 8)

# AWS Configuration (if using S3)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AUTOSCORER_S3_BUCKET=your-s3-bucket
EOF
        log_info ".env file created with random secrets."
    else
        log_info ".env file already exists."
    fi
    
    # 创建配置目录
    mkdir -p config/nginx config/postgres
    
    if [[ ! -f config/config.yaml ]]; then
        log_info "Creating default config.yaml..."
        cp config.yaml config/config.yaml 2>/dev/null || log_warn "No default config found"
    fi
}

# Docker 部署
deploy_docker() {
    log_info "Starting Docker deployment..."
    
    # 构建镜像 (如果需要)
    if [[ "$BUILD_IMAGE" == "true" ]]; then
        log_info "Building AutoScorer Docker image..."
        docker build -t autoscorer:latest .
    fi
    
    # 启动服务
    log_info "Starting services with Docker Compose..."
  docker compose up -d
    
    # 等待服务启动
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # 健康检查
  if curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
        log_info "AutoScorer is running successfully!"
        log_info "API: http://localhost:8000"
        log_info "Flower (Celery monitoring): http://localhost:5555"
    else
    log_error "AutoScorer failed to start. Check logs with: docker compose logs"
        exit 1
    fi
}

# Kubernetes 部署
deploy_kubernetes() {
    log_info "Starting Kubernetes deployment..."
    
    # 检查 kubectl 连接
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    # 创建命名空间
    log_info "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml 2>/dev/null || log_warn "Namespace may already exist"
    
    # 创建配置和密钥
    log_info "Creating ConfigMaps and Secrets..."
    if [[ -f config/config.yaml ]]; then
        kubectl create configmap autoscorer-config \
            --from-file=config.yaml=config/config.yaml \
            --namespace=autoscorer \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    # 从 .env 文件创建 Secret
    if [[ -f .env ]]; then
        kubectl create secret generic autoscorer-secrets \
            --from-env-file=.env \
            --namespace=autoscorer \
            --dry-run=client -o yaml | kubectl apply -f -
    fi
    
    # 部署所有资源
    log_info "Deploying AutoScorer resources..."
    kubectl apply -f k8s/ 2>/dev/null || log_warn "Some resources may already exist"
    
    # 等待部署完成
    log_info "Waiting for deployment to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/autoscorer -n autoscorer
    
    # 获取访问地址
    log_info "Getting service information..."
    kubectl get ingress autoscorer-ingress -n autoscorer 2>/dev/null || log_warn "Ingress not found"
}

# 部署验证
verify_deployment() {
    log_info "Verifying deployment..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
        API_URL="http://localhost:8000"
    else
        # Kubernetes - 使用端口转发测试
        kubectl port-forward service/autoscorer-service 8000:80 -n autoscorer &
        PORT_FORWARD_PID=$!
        sleep 5
        API_URL="http://localhost:8000"
    fi
    
    # 健康检查
  if curl -f "$API_URL/healthz" > /dev/null 2>&1; then
        log_info "✓ Health check passed"
    else
        log_error "✗ Health check failed"
        if [[ "$DEPLOYMENT_TYPE" == "kubernetes" && -n "$PORT_FORWARD_PID" ]]; then
            kill $PORT_FORWARD_PID 2>/dev/null || true
        fi
        return 1
    fi
    
    # API 测试
    if curl -f "$API_URL/api/v1/scorers" > /dev/null 2>&1; then
        log_info "✓ API endpoints accessible"
    else
        log_error "✗ API endpoints not accessible"
        if [[ "$DEPLOYMENT_TYPE" == "kubernetes" && -n "$PORT_FORWARD_PID" ]]; then
            kill $PORT_FORWARD_PID 2>/dev/null || true
        fi
        return 1
    fi
    
    if [[ "$DEPLOYMENT_TYPE" == "kubernetes" && -n "$PORT_FORWARD_PID" ]]; then
        kill $PORT_FORWARD_PID 2>/dev/null || true
    fi
    
    log_info "Deployment verification completed successfully!"
}

# 清理部署
cleanup() {
    log_info "Cleaning up deployment..."
    
    if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
  docker compose down -v
        docker system prune -f
    else
        kubectl delete namespace autoscorer 2>/dev/null || log_warn "Namespace may not exist"
    fi
    
    log_info "Cleanup completed."
}

# 主函数
main() {
    # 解析命令行参数
    DEPLOYMENT_TYPE="docker"
    BUILD_IMAGE="false"
    CLEANUP="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --kubernetes|-k)
                DEPLOYMENT_TYPE="kubernetes"
                shift
                ;;
            --build|-b)
                BUILD_IMAGE="true"
                shift
                ;;
            --cleanup|-c)
                CLEANUP="true"
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --kubernetes, -k    Deploy to Kubernetes"
                echo "  --build, -b         Build Docker image before deployment"
                echo "  --cleanup, -c       Cleanup existing deployment"
                echo "  --help, -h          Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "Starting AutoScorer deployment..."
    log_info "Deployment type: $DEPLOYMENT_TYPE"
    
    if [[ "$CLEANUP" == "true" ]]; then
        cleanup
        exit 0
    fi
    
    check_dependencies
    generate_config
    
  if [[ "$DEPLOYMENT_TYPE" == "docker" ]]; then
    deploy_docker
  else
        deploy_kubernetes
    fi
    
    verify_deployment
    
    log_info "AutoScorer deployment completed successfully!"
}

# 执行主函数
main "$@"
```

## 故障排除

### 常见故障与排查步骤

1. **容器启动失败**

```bash
# 查看容器日志
docker compose logs api
docker compose logs worker

# 检查容器状态
docker compose ps

# 进入容器调试
docker compose exec api bash
```

1. **Kubernetes Pod 启动失败**

```bash
# 查看 Pod 状态
kubectl get pods -n autoscorer

# 查看 Pod 日志
kubectl logs -f deployment/autoscorer -n autoscorer

# 描述 Pod 事件
kubectl describe pod <pod-name> -n autoscorer
```

1. **网络连接问题**

```bash
# 测试 Redis 连接
kubectl exec -it deployment/autoscorer -n autoscorer -- redis-cli -h redis-service ping

# 测试数据库连接 (如果使用)
kubectl exec -it deployment/autoscorer -n autoscorer -- psql -h postgres-service -U autoscorer -d autoscorer -c '\\l'
```

1. **性能问题**

```bash
# 查看资源使用情况
kubectl top nodes
kubectl top pods -n autoscorer

# 调整资源限制
kubectl patch deployment autoscorer -n autoscorer -p '{"spec":{"template":{"spec":{"containers":[{"name":"autoscorer","resources":{"requests":{"memory":"2Gi","cpu":"1000m"},"limits":{"memory":"4Gi","cpu":"2000m"}}}]}}}}'
```

## 相关文档

- **[配置管理](configuration.md)** - 详细配置选项
- **[开发指南](development.md)** - 开发环境搭建
- **[错误处理](error-handling.md)** - 常见问题解决
- **[API 参考](api-reference.md)** - API 接口文档
