# 部署指南

本文档详细说明 AutoScorer 系统的部署方法，包括 Docker 部署、Kubernetes 部署、云服务部署和运维管理。

## 快速部署

### Docker 单容器部署

```bash
# 1. 拉取镜像
docker pull autoscorer:latest

# 2. 创建网络
docker network create autoscorer-network

# 3. 启动 Redis
docker run -d \
  --name redis \
  --network autoscorer-network \
  redis:7-alpine

# 4. 启动 AutoScorer
docker run -d \
  --name autoscorer \
  --network autoscorer-network \
  -p 8000:8000 \
  -e REDIS_HOST=redis \
  -v $(pwd)/workspaces:/var/lib/autoscorer/workspaces \
  -v $(pwd)/results:/var/lib/autoscorer/results \
  autoscorer:latest

# 5. 验证部署
curl http://localhost:8000/health
```

### Docker Compose 部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  # AutoScorer 主服务
  autoscorer:
    image: autoscorer:latest
    ports:
      - "8000:8000"
    environment:
      # 环境配置
      AUTOSCORER_ENV: production
      AUTOSCORER_DEBUG: "false"
      
      # Redis 连接
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      
      # 安全配置
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      AUTOSCORER_API_KEY: ${AUTOSCORER_API_KEY}
      
      # 存储配置
      AUTOSCORER_WORKSPACE_PATH: /var/lib/autoscorer/workspaces
      AUTOSCORER_RESULTS_PATH: /var/lib/autoscorer/results
      AUTOSCORER_RESULTS_BACKEND: filesystem
      
      # 日志配置
      AUTOSCORER_LOG_LEVEL: INFO
      AUTOSCORER_LOG_FILE: /var/log/autoscorer.log
      
    volumes:
      # 配置文件
      - ./config/config.yaml:/app/config.yaml:ro
      
      # 数据目录
      - autoscorer-workspaces:/var/lib/autoscorer/workspaces
      - autoscorer-results:/var/lib/autoscorer/results
      - autoscorer-logs:/var/log
      
      # 自定义评分器
      - ./custom_scorers:/app/custom_scorers:ro
      
      # Docker socket (用于 Docker 执行器)
      - /var/run/docker.sock:/var/run/docker.sock
      
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Celery Worker
  worker:
    image: autoscorer:latest
    command: celery -A autoscorer.celery_app.worker worker --loglevel=info
    environment:
      # 继承主服务环境变量
      AUTOSCORER_ENV: production
      REDIS_HOST: redis
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      
      # Worker 特定配置
      CELERY_WORKERS: 4
      CELERY_LOG_LEVEL: INFO
      
    volumes:
      - ./config/config.yaml:/app/config.yaml:ro
      - autoscorer-workspaces:/var/lib/autoscorer/workspaces
      - autoscorer-results:/var/lib/autoscorer/results
      - ./custom_scorers:/app/custom_scorers:ro
      - /var/run/docker.sock:/var/run/docker.sock
      
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    deploy:
      replicas: 2

  # Celery Beat (定时任务调度器)
  beat:
    image: autoscorer:latest
    command: celery -A autoscorer.celery_app.worker beat --loglevel=info
    environment:
      AUTOSCORER_ENV: production
      REDIS_HOST: redis
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      
    volumes:
      - ./config/config.yaml:/app/config.yaml:ro
      - celery-beat-schedule:/app/celerybeat-schedule
      
    depends_on:
      - redis
    restart: unless-stopped

  # Celery Flower (监控界面)
  flower:
    image: autoscorer:latest
    command: celery -A autoscorer.celery_app.worker flower --port=5555
    ports:
      - "5555:5555"
    environment:
      REDIS_HOST: redis
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      FLOWER_BASIC_AUTH: ${FLOWER_BASIC_AUTH}  # user:password
      
    depends_on:
      - redis
    restart: unless-stopped

  # Redis 缓存和消息队列
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
      - ./config/redis.conf:/usr/local/etc/redis/redis.conf:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # PostgreSQL 数据库 (可选，用于结果存储)
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: autoscorer
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./config/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Nginx 反向代理 (可选)
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/nginx/ssl:/etc/nginx/ssl:ro
      - nginx-logs:/var/log/nginx
    depends_on:
      - autoscorer
    restart: unless-stopped

volumes:
  autoscorer-workspaces:
    driver: local
  autoscorer-results:
    driver: local
  autoscorer-logs:
    driver: local
  redis-data:
    driver: local
  postgres-data:
    driver: local
  celery-beat-schedule:
    driver: local
  nginx-logs:
    driver: local

networks:
  default:
    name: autoscorer-network
```

### 环境变量文件

```bash
# .env
# 安全密钥 (生产环境必须更改)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
AUTOSCORER_API_KEY=your-api-key-change-this-in-production
REDIS_PASSWORD=your-redis-password-change-this

# 数据库配置
POSTGRES_USER=autoscorer
POSTGRES_PASSWORD=your-postgres-password-change-this

# Flower 监控认证
FLOWER_BASIC_AUTH=admin:your-flower-password

# 云服务配置 (如果使用)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AUTOSCORER_S3_BUCKET=your-s3-bucket
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
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
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

### 自动化部署脚本

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
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose first."
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
    docker-compose up -d
    
    # 等待服务启动
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # 健康检查
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_info "AutoScorer is running successfully!"
        log_info "API: http://localhost:8000"
        log_info "Flower (Celery monitoring): http://localhost:5555"
    else
        log_error "AutoScorer failed to start. Check logs with: docker-compose logs"
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
    if curl -f "$API_URL/health" > /dev/null 2>&1; then
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
        docker-compose down -v
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

### 常见问题

1. **容器启动失败**
```bash
# 查看容器日志
docker-compose logs autoscorer

# 检查容器状态
docker-compose ps

# 进入容器调试
docker-compose exec autoscorer bash
```

2. **Kubernetes Pod 启动失败**
```bash
# 查看 Pod 状态
kubectl get pods -n autoscorer

# 查看 Pod 日志
kubectl logs -f deployment/autoscorer -n autoscorer

# 描述 Pod 事件
kubectl describe pod <pod-name> -n autoscorer
```

3. **网络连接问题**
```bash
# 测试 Redis 连接
kubectl exec -it deployment/autoscorer -n autoscorer -- redis-cli -h redis-service ping

# 测试数据库连接 (如果使用)
kubectl exec -it deployment/autoscorer -n autoscorer -- psql -h postgres-service -U autoscorer -d autoscorer -c '\l'
```

4. **性能问题**
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
