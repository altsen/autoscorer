# 平台集成指南

本文档详细说明如何将 AutoScorer 系统集成到第三方平台中，包括 API 设计、权限管理、任务调度和结果处理等关键环节。

## 集成架构概览

### 系统架构

```mermaid
graph TB
    subgraph "第三方平台"
        A[Web 界面]
        B[后台服务]
        C[数据库]
    end
    
    subgraph "AutoScorer 系统"
        D[API 网关]
        E[任务调度器]
        F[执行引擎]
        G[结果存储]
    end
    
    subgraph "通信机制"
        H[REST API]
        I[Webhook 回调]
        J[消息队列]
    end
    
    A --> B
    B --> C
    B <--> H
    H <--> D
    D --> E
    E --> F
    F --> G
    G --> I
    I --> B
    E <--> J
    
    style D fill:#e3f2fd
    style E fill:#fff3e0
    style F fill:#e8f5e8
    style G fill:#f3e5f5
```

### 集成模式

| 集成模式 | 适用场景 | 技术要求 | 集成复杂度 |
|----------|----------|----------|------------|
| **API 调用** | 在线评测平台 | HTTP/REST | 低 |
| **SDK 集成** | 深度定制 | Python/Docker | 中 |
| **容器化部署** | 独立部署 | K8s/Docker Compose | 高 |
| **微服务架构** | 大型平台 | 服务网格 | 高 |

## API 集成方案

### 认证与授权

#### JWT 认证

```python
# 生成 JWT Token
import jwt
import datetime

def generate_token(user_id: str, platform_id: str) -> str:
    payload = {
        'user_id': user_id,
        'platform_id': platform_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        'iat': datetime.datetime.utcnow(),
        'scope': ['submit_job', 'query_result']
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

# 使用 Token
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
```

#### API Key 认证

```python
# 简单 API Key 认证
headers = {
    'X-API-Key': 'your_api_key_here',
    'Content-Type': 'application/json'
}
```

### 核心 API 接口

#### 1. 任务提交接口

**POST** `/api/v1/jobs`

```python
import requests
import json

def submit_job(workspace_data: dict, scorer: str, callback_url: str = None) -> dict:
    """提交评分任务"""
    payload = {
        'workspace': workspace_data,
        'scorer': scorer,
        'callback_url': callback_url,
        'priority': 'normal',  # low, normal, high
        'timeout': 1800,  # 30 分钟
        'resources': {
            'memory': '2Gi',
            'cpu': '1000m',
            'gpu': 0
        }
    }
    
    response = requests.post(
        'https://autoscorer.example.com/api/v1/jobs',
        headers=headers,
        json=payload
    )
    
    return response.json()

# 示例响应
{
    "ok": true,
    "data": {
        "job_id": "job_abc123",
        "status": "pending",
        "estimated_time": 120,
        "queue_position": 3
    },
    "meta": {
        "timestamp": "2025-09-01T10:30:00Z",
        "request_id": "req_456"
    }
}
```

#### 2. 任务状态查询

**GET** `/api/v1/jobs/{job_id}`

```python
def get_job_status(job_id: str) -> dict:
    """查询任务状态"""
    response = requests.get(
        f'https://autoscorer.example.com/api/v1/jobs/{job_id}',
        headers=headers
    )
    
    return response.json()

# 示例响应
{
    "ok": true,
    "data": {
        "job_id": "job_abc123",
        "status": "running",
        "progress": 65,
        "stage": "scoring",
        "elapsed_time": 78,
        "estimated_remaining": 42
    }
}
```

#### 3. 结果获取接口

**GET** `/api/v1/jobs/{job_id}/result`

```python
def get_job_result(job_id: str) -> dict:
    """获取评分结果"""
    response = requests.get(
        f'https://autoscorer.example.com/api/v1/jobs/{job_id}/result',
        headers=headers
    )
    
    return response.json()

# 示例响应
{
    "ok": true,
    "data": {
        "job_id": "job_abc123",
        "status": "completed",
        "result": {
            // 完整的评分结果 (符合 output-standards.md)
        },
        "artifacts": {
            "download_urls": [
                "https://storage.example.com/results/job_abc123/confusion_matrix.png"
            ]
        }
    }
}
```

#### 4. 日志查询接口

**GET** `/api/v1/jobs/{job_id}/logs`

```python
def get_job_logs(job_id: str, level: str = 'INFO') -> dict:
    """获取任务日志"""
    params = {'level': level, 'limit': 100}
    
    response = requests.get(
        f'https://autoscorer.example.com/api/v1/jobs/{job_id}/logs',
        headers=headers,
        params=params
    )
    
    return response.json()
```

### 批量操作接口

#### 批量任务提交

```python
def submit_batch_jobs(jobs: list) -> dict:
    """批量提交任务"""
    payload = {
        'jobs': jobs,
        'batch_callback_url': 'https://platform.example.com/batch_callback'
    }
    
    response = requests.post(
        'https://autoscorer.example.com/api/v1/jobs/batch',
        headers=headers,
        json=payload
    )
    
    return response.json()
```

## Webhook 回调机制

### 回调配置

```python
# 平台端回调处理
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)

@app.route('/autoscorer/callback', methods=['POST'])
def handle_callback():
    """处理 AutoScorer 回调"""
    
    # 验证签名
    signature = request.headers.get('X-AutoScorer-Signature')
    if not verify_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    callback_data = request.json
    job_id = callback_data['job_id']
    status = callback_data['status']
    
    if status == 'completed':
        # 处理成功回调
        result = callback_data['result']
        update_platform_result(job_id, result)
        
    elif status == 'failed':
        # 处理失败回调
        error = callback_data['error']
        update_platform_error(job_id, error)
    
    return jsonify({'received': True})

def verify_signature(payload: bytes, signature: str) -> bool:
    """验证回调签名"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f'sha256={expected}', signature)
```

### 回调数据格式

#### 成功回调

```json
{
    "job_id": "job_abc123",
    "status": "completed",
    "result": {
        // 完整评分结果
    },
    "execution_time": 145.6,
    "timestamp": "2025-09-01T11:00:00Z",
    "signature": "sha256=..."
}
```

#### 失败回调

```json
{
    "job_id": "job_abc123",
    "status": "failed",
    "error": {
        "code": "EXE_SCORER_EXECUTION_FAILED",
        "message": "Scorer execution failed",
        "stage": "scoring",
        "details": {}
    },
    "timestamp": "2025-09-01T11:00:00Z"
}
```

## SDK 集成方案

### Python SDK

```python
# autoscorer_client.py
from typing import Optional, Dict, Any
import requests
import time

class AutoScorerClient:
    """AutoScorer 客户端 SDK"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def submit_job(self, workspace: Dict[str, Any], scorer: str, 
                   **kwargs) -> str:
        """提交评分任务"""
        payload = {
            'workspace': workspace,
            'scorer': scorer,
            **kwargs
        }
        
        response = self.session.post(
            f'{self.base_url}/api/v1/jobs',
            json=payload
        )
        
        response.raise_for_status()
        return response.json()['data']['job_id']
    
    def wait_for_completion(self, job_id: str, 
                          timeout: int = 3600) -> Dict[str, Any]:
        """等待任务完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            
            if status['status'] == 'completed':
                return self.get_job_result(job_id)
            elif status['status'] == 'failed':
                raise Exception(f"Job failed: {status.get('error')}")
            
            time.sleep(10)  # 每 10 秒查询一次
        
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        response = self.session.get(f'{self.base_url}/api/v1/jobs/{job_id}')
        response.raise_for_status()
        return response.json()['data']
    
    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """获取任务结果"""
        response = self.session.get(f'{self.base_url}/api/v1/jobs/{job_id}/result')
        response.raise_for_status()
        return response.json()['data']

# 使用示例
client = AutoScorerClient(
    base_url='https://autoscorer.example.com',
    api_key='your_api_key'
)

# 提交任务
job_id = client.submit_job(
    workspace={
        'gt_file': 'gt.csv',
        'pred_file': 'pred.csv'
    },
    scorer='classification_f1'
)

# 等待完成并获取结果
result = client.wait_for_completion(job_id)
print(f"Score: {result['result']['summary']['score']}")
```

### JavaScript SDK

```javascript
// autoscorer-client.js
class AutoScorerClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
    }
    
    async submitJob(workspace, scorer, options = {}) {
        const payload = {
            workspace,
            scorer,
            ...options
        };
        
        const response = await fetch(`${this.baseUrl}/api/v1/jobs`, {
            method: 'POST',
            headers: {
                'X-API-Key': this.apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data.data.job_id;
    }
    
    async waitForCompletion(jobId, timeout = 3600000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            const status = await this.getJobStatus(jobId);
            
            if (status.status === 'completed') {
                return await this.getJobResult(jobId);
            } else if (status.status === 'failed') {
                throw new Error(`Job failed: ${status.error}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 10000)); // 10秒间隔
        }
        
        throw new Error(`Job ${jobId} did not complete within timeout`);
    }
    
    async getJobStatus(jobId) {
        const response = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}`, {
            headers: {
                'X-API-Key': this.apiKey
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data.data;
    }
    
    async getJobResult(jobId) {
        const response = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}/result`, {
            headers: {
                'X-API-Key': this.apiKey
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data.data;
    }
}

// 使用示例
const client = new AutoScorerClient(
    'https://autoscorer.example.com',
    'your_api_key'
);

async function runEvaluation() {
    try {
        const jobId = await client.submitJob(
            {
                gt_file: 'gt.csv',
                pred_file: 'pred.csv'
            },
            'classification_f1'
        );
        
        console.log(`Job submitted: ${jobId}`);
        
        const result = await client.waitForCompletion(jobId);
        console.log(`Score: ${result.result.summary.score}`);
        
    } catch (error) {
        console.error('Evaluation failed:', error);
    }
}
```

## 权限与安全管理

### 访问控制列表 (ACL)

```python
# 权限配置示例
PLATFORM_PERMISSIONS = {
    'platform_a': {
        'allowed_scorers': ['classification_*', 'regression_*'],
        'max_concurrent_jobs': 10,
        'max_job_duration': 3600,
        'allowed_callbacks': ['https://platform-a.com/*'],
        'resource_limits': {
            'memory': '4Gi',
            'cpu': '2000m',
            'gpu': 1
        }
    },
    'platform_b': {
        'allowed_scorers': ['*'],
        'max_concurrent_jobs': 50,
        'max_job_duration': 7200,
        'allowed_callbacks': ['https://platform-b.com/*'],
        'resource_limits': {
            'memory': '8Gi',
            'cpu': '4000m',
            'gpu': 2
        }
    }
}
```

### 请求限流

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 基于 IP 的限流
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"]
)

@app.route('/api/v1/jobs', methods=['POST'])
@limiter.limit("10 per minute")
def submit_job():
    """提交任务接口 (限制每分钟 10 次)"""
    pass

# 基于 API Key 的限流
@app.route('/api/v1/jobs', methods=['POST'])
@limiter.limit("100 per hour", key_func=lambda: get_api_key())
def submit_job_with_api_key():
    """基于 API Key 的限流"""
    pass
```

## 数据格式与转换

### 工作区数据结构

```python
# 标准工作区结构
{
    "gt_file": "ground_truth.csv",  # 必需
    "pred_file": "predictions.csv", # 必需
    "meta": {                       # 可选
        "dataset": "test_set_v1",
        "submission_id": "sub_123",
        "user_id": "user_456"
    },
    "parameters": {                 # 可选
        "threshold": 0.5,
        "metric_config": {
            "average": "macro"
        }
    }
}
```

### 数据格式转换器

```python
class DataFormatConverter:
    """数据格式转换器"""
    
    @staticmethod
    def convert_kaggle_format(submission_file: str, truth_file: str) -> dict:
        """转换 Kaggle 竞赛格式"""
        return {
            'gt_file': truth_file,
            'pred_file': submission_file,
            'meta': {
                'format': 'kaggle',
                'converted_at': datetime.utcnow().isoformat()
            }
        }
    
    @staticmethod
    def convert_coco_format(pred_json: str, gt_json: str) -> dict:
        """转换 COCO 检测格式"""
        return {
            'gt_file': gt_json,
            'pred_file': pred_json,
            'meta': {
                'format': 'coco',
                'task_type': 'detection'
            }
        }
    
    @staticmethod
    def convert_custom_format(data: dict, format_spec: dict) -> dict:
        """自定义格式转换"""
        # 实现自定义转换逻辑
        pass
```

## 错误处理与重试机制

### 错误处理策略

```python
import backoff
import requests

class AutoScorerAPI:
    """带错误处理的 API 客户端"""
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, requests.exceptions.Timeout),
        max_tries=3,
        max_time=300
    )
    def submit_job_with_retry(self, payload: dict) -> dict:
        """带重试的任务提交"""
        response = self.session.post(
            f'{self.base_url}/api/v1/jobs',
            json=payload,
            timeout=30
        )
        
        # 对于 5xx 错误进行重试
        if response.status_code >= 500:
            response.raise_for_status()
        
        # 对于 4xx 错误不重试
        if response.status_code >= 400:
            error_data = response.json()
            raise APIError(
                status_code=response.status_code,
                error_code=error_data.get('error', {}).get('code'),
                message=error_data.get('error', {}).get('message')
            )
        
        return response.json()

class APIError(Exception):
    """API 错误异常"""
    
    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"{error_code}: {message}")
```

### 熔断器模式

```python
import time
from typing import Callable, Any

class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """调用带熔断保护的函数"""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
            else:
                raise CircuitBreakerError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """成功回调"""
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'

# 使用示例
circuit_breaker = CircuitBreaker()

def protected_api_call():
    return circuit_breaker.call(api_client.submit_job, payload)
```

## 监控与日志

### 集成监控指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义监控指标
job_submissions = Counter('autoscorer_job_submissions_total', 'Total job submissions', ['platform', 'scorer'])
job_duration = Histogram('autoscorer_job_duration_seconds', 'Job execution duration')
active_jobs = Gauge('autoscorer_active_jobs', 'Number of active jobs', ['platform'])

def track_job_submission(platform: str, scorer: str):
    """记录任务提交指标"""
    job_submissions.labels(platform=platform, scorer=scorer).inc()

def track_job_completion(duration: float):
    """记录任务完成指标"""
    job_duration.observe(duration)

def update_active_jobs(platform: str, count: int):
    """更新活跃任务数"""
    active_jobs.labels(platform=platform).set(count)
```

### 结构化日志

```python
import structlog

logger = structlog.get_logger()

def log_job_event(event: str, job_id: str, **kwargs):
    """记录任务事件"""
    logger.info(
        event,
        job_id=job_id,
        timestamp=datetime.utcnow().isoformat(),
        **kwargs
    )

# 使用示例
log_job_event(
    "job_submitted",
    job_id="job_123",
    platform="platform_a",
    scorer="classification_f1",
    user_id="user_456"
)
```

## 部署配置示例

### Docker Compose 集成

```yaml
# docker-compose.integration.yml
version: '3.8'

services:
  platform-backend:
    image: platform/backend:latest
    environment:
      - AUTOSCORER_API_URL=http://autoscorer-api:8000
      - AUTOSCORER_API_KEY=${AUTOSCORER_API_KEY}
    depends_on:
      - autoscorer-api
    networks:
      - platform-network

  autoscorer-api:
    image: autoscorer/api:latest
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/autoscorer
    depends_on:
      - redis
      - postgres
    networks:
      - platform-network

  autoscorer-worker:
    image: autoscorer/worker:latest
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/autoscorer
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - redis
      - postgres
    networks:
      - platform-network

  redis:
    image: redis:alpine
    networks:
      - platform-network

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=autoscorer
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    networks:
      - platform-network

networks:
  platform-network:
    driver: bridge
```

### Kubernetes 集成

```yaml
# autoscorer-integration.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscorer-config
data:
  config.yaml: |
    api:
      host: "0.0.0.0"
      port: 8000
      cors_origins: ["https://platform.example.com"]
    
    security:
      api_keys:
        platform_a: "api_key_for_platform_a"
        platform_b: "api_key_for_platform_b"
      
      rate_limits:
        platform_a:
          requests_per_minute: 100
          max_concurrent_jobs: 10
        platform_b:
          requests_per_minute: 200
          max_concurrent_jobs: 20

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autoscorer-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: autoscorer-api
  template:
    metadata:
      labels:
        app: autoscorer-api
    spec:
      containers:
      - name: api
        image: autoscorer/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: CONFIG_FILE
          value: /config/config.yaml
        volumeMounts:
        - name: config
          mountPath: /config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      volumes:
      - name: config
        configMap:
          name: autoscorer-config

---
apiVersion: v1
kind: Service
metadata:
  name: autoscorer-api-service
spec:
  selector:
    app: autoscorer-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

## 集成示例：Kaggle 风格平台

```python
# kaggle_integration.py
class KaggleStyleIntegration:
    """Kaggle 风格竞赛平台集成示例"""
    
    def __init__(self):
        self.autoscorer_client = AutoScorerClient(
            base_url=settings.AUTOSCORER_URL,
            api_key=settings.AUTOSCORER_API_KEY
        )
    
    def submit_evaluation(self, competition_id: str, team_id: str, 
                         submission_file: str) -> dict:
        """提交评测任务"""
        
        # 获取竞赛配置
        competition = Competition.objects.get(id=competition_id)
        
        # 准备工作区数据
        workspace = {
            'gt_file': competition.ground_truth_file,
            'pred_file': submission_file,
            'meta': {
                'competition_id': competition_id,
                'team_id': team_id,
                'submission_time': datetime.utcnow().isoformat()
            }
        }
        
        # 提交任务
        job_id = self.autoscorer_client.submit_job(
            workspace=workspace,
            scorer=competition.scorer,
            callback_url=f"{settings.BASE_URL}/evaluation/callback",
            priority='high' if competition.is_final_phase else 'normal'
        )
        
        # 记录提交
        submission = Submission.objects.create(
            competition=competition,
            team_id=team_id,
            job_id=job_id,
            status='pending',
            submitted_at=datetime.utcnow()
        )
        
        return {
            'submission_id': submission.id,
            'job_id': job_id,
            'status': 'pending'
        }
    
    def handle_callback(self, callback_data: dict):
        """处理评测回调"""
        job_id = callback_data['job_id']
        
        try:
            submission = Submission.objects.get(job_id=job_id)
        except Submission.DoesNotExist:
            logger.error(f"Submission not found for job {job_id}")
            return
        
        if callback_data['status'] == 'completed':
            result = callback_data['result']
            
            # 更新提交记录
            submission.status = 'completed'
            submission.score = result['summary']['score']
            submission.result_data = result
            submission.completed_at = datetime.utcnow()
            submission.save()
            
            # 更新排行榜
            self.update_leaderboard(submission)
            
            # 发送通知
            self.notify_team(submission.team_id, 'evaluation_completed', {
                'score': submission.score,
                'rank': self.get_team_rank(submission.team_id, submission.competition_id)
            })
            
        elif callback_data['status'] == 'failed':
            submission.status = 'failed'
            submission.error_message = callback_data['error']['message']
            submission.completed_at = datetime.utcnow()
            submission.save()
            
            # 发送错误通知
            self.notify_team(submission.team_id, 'evaluation_failed', {
                'error': submission.error_message
            })
    
    def update_leaderboard(self, submission: Submission):
        """更新排行榜"""
        # 实现排行榜更新逻辑
        pass
    
    def notify_team(self, team_id: str, event: str, data: dict):
        """发送团队通知"""
        # 实现通知逻辑 (邮件、WebSocket、Push 等)
        pass
```

## 测试与调试

### API 集成测试

```python
import pytest
import requests_mock

class TestAutoScorerIntegration:
    """AutoScorer 集成测试"""
    
    def test_job_submission_success(self, requests_mock):
        """测试成功提交任务"""
        requests_mock.post(
            'https://autoscorer.example.com/api/v1/jobs',
            json={
                'ok': True,
                'data': {
                    'job_id': 'job_123',
                    'status': 'pending'
                }
            }
        )
        
        client = AutoScorerClient(
            'https://autoscorer.example.com',
            'test_api_key'
        )
        
        job_id = client.submit_job(
            workspace={'gt_file': 'gt.csv', 'pred_file': 'pred.csv'},
            scorer='classification_f1'
        )
        
        assert job_id == 'job_123'
    
    def test_job_submission_failure(self, requests_mock):
        """测试任务提交失败"""
        requests_mock.post(
            'https://autoscorer.example.com/api/v1/jobs',
            status_code=400,
            json={
                'ok': False,
                'error': {
                    'code': 'VAL_INVALID_SCORER',
                    'message': 'Invalid scorer name'
                }
            }
        )
        
        client = AutoScorerClient(
            'https://autoscorer.example.com',
            'test_api_key'
        )
        
        with pytest.raises(APIError) as exc_info:
            client.submit_job(
                workspace={'gt_file': 'gt.csv', 'pred_file': 'pred.csv'},
                scorer='invalid_scorer'
            )
        
        assert exc_info.value.error_code == 'VAL_INVALID_SCORER'
```

### 端到端测试

```python
def test_end_to_end_evaluation():
    """端到端评测测试"""
    
    # 1. 准备测试数据
    workspace = prepare_test_workspace()
    
    # 2. 提交任务
    client = AutoScorerClient(TEST_API_URL, TEST_API_KEY)
    job_id = client.submit_job(workspace, 'classification_f1')
    
    # 3. 等待完成
    result = client.wait_for_completion(job_id, timeout=300)
    
    # 4. 验证结果
    assert result['status'] == 'completed'
    assert 'score' in result['result']['summary']
    assert 0.0 <= result['result']['summary']['score'] <= 1.0
    
    # 5. 验证产物
    assert 'artifacts' in result['result']
    assert len(result['result']['artifacts']) > 0
```

## 相关文档

- **[API 参考](api-reference.md)** - 详细 API 接口文档
- **[输出标准](output-standards.md)** - 标准化输出格式
- **[错误处理](error-handling.md)** - 错误处理和故障排查
- **[部署指南](deployment.md)** - 生产环境部署配置
