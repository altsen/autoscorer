from __future__ import annotations
from pathlib import Path
from .base import Executor
from ..schemas.job import JobSpec
from autoscorer.utils.config import Config
from autoscorer.utils.errors import AutoscorerError
import logging

logger = logging.getLogger(__name__)


class K8sExecutor(Executor):
    """Kubernetes执行器 - 改进实现"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.cfg = Config(config_path)
        self.namespace = self.cfg.get("K8S_NAMESPACE", "autoscore")
        self.api_server = self.cfg.get("K8S_API")
        self.token = self.cfg.get("K8S_TOKEN")
        self.ca_cert = self.cfg.get("K8S_CA_CERT")

        if not self.api_server:
            raise AutoscorerError(
                code="K8S_CONFIG_ERROR",
                message="K8S_API not configured"
            )
    
    def run(self, spec: JobSpec, workspace: Path) -> None:
        """使用Kubernetes Job执行容器任务
        
        注意：这是一个基础实现，生产环境需要完善以下功能：
        - PV/PVC挂载workspace
        - 实时日志收集
        - 作业状态监控
        - 资源配额验证
        - 安全策略配置
        """
        try:
            # 尝试导入kubernetes客户端
            import kubernetes
            from kubernetes.client.rest import ApiException
        except ImportError:
            raise AutoscorerError(
                code="K8S_CLIENT_ERROR",
                message="kubernetes client not installed. Run: pip install kubernetes"
            )
        
        logger.info(f"Creating K8s Job for {spec.job_id}")
        
        try:
            # 配置K8s客户端
            if self.token:
                # 使用Token认证
                configuration = kubernetes.client.Configuration()
                configuration.host = self.api_server
                configuration.api_key["authorization"] = self.token
                configuration.api_key_prefix['authorization'] = 'Bearer'
                if self.ca_cert:
                    configuration.ssl_ca_cert = self.ca_cert
                else:
                    configuration.verify_ssl = False
                kubernetes.client.Configuration.set_default(configuration)
            else:
                # 使用集群内配置或kubeconfig
                try:
                    kubernetes.config.load_incluster_config()
                except:
                    kubernetes.config.load_kube_config()
            
            # 创建Job规范
            job_manifest = self._create_job_manifest(spec, workspace)
            
            # 提交Job
            batch_v1 = kubernetes.client.BatchV1Api()
            job = batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_manifest
            )
            
            logger.info(f"Created K8s Job: {job.metadata.name}")
            
            # 等待Job完成 (简化实现)
            self._wait_for_job_completion(batch_v1, job.metadata.name)
            
        except ApiException as e:
            raise AutoscorerError(
                code="K8S_API_ERROR",
                message=f"K8s API error: {e.status} - {e.reason}",
                details={"status": e.status, "reason": e.reason}
            )
        except Exception as e:
            raise AutoscorerError(
                code="K8S_EXEC_ERROR",
                message=f"K8s execution failed: {str(e)}"
            )
    
    def _create_job_manifest(self, spec: JobSpec, workspace: Path):
        """创建Kubernetes Job清单"""
        import kubernetes.client as client
        
        # 规范化镜像引用（与 DockerExecutor 保持一致，未带 tag 则默认 latest）
        def _parse_repo_tag(ref: str):
            try:
                from docker.utils import utils as docker_utils  # type: ignore
                repo, tag = docker_utils.parse_repository_tag(ref)
                return repo, tag
            except Exception:
                slash = ref.rfind('/')
                colon = ref.rfind(':')
                if colon > slash:
                    return ref[:colon], ref[colon + 1:]
                return ref, None
        repo, tag = _parse_repo_tag(spec.container.image)
        normalized_ref = f"{repo}:{tag or 'latest'}"
        
        # 容器规范
        container = client.V1Container(
            name="autoscorer-job",
            image=normalized_ref,
            command=spec.container.cmd or [],
            env=[
                client.V1EnvVar(name=k, value=v) 
                for k, v in spec.container.env.items()
            ],
            resources=client.V1ResourceRequirements(
                requests={
                    "cpu": str(spec.resources.cpu),
                    "memory": spec.resources.memory
                },
                limits={
                    "cpu": str(spec.resources.cpu * 2),  # 允许突发
                    "memory": spec.resources.memory
                }
            ),
            working_dir="/workspace",
            volume_mounts=[
                client.V1VolumeMount(
                    name="workspace",
                    mount_path="/workspace"
                )
            ]
        )
        
        # 如果需要GPU
        if spec.resources.gpus > 0:
            if not container.resources.limits:
                container.resources.limits = {}
            container.resources.limits["nvidia.com/gpu"] = str(spec.resources.gpus)
        
        # Pod规范
        pod_spec = client.V1PodSpec(
            containers=[container],
            restart_policy="Never",
            volumes=[
                client.V1Volume(
                    name="workspace",
                    empty_dir=client.V1EmptyDirVolumeSource()
                )
            ],
            security_context=client.V1PodSecurityContext(
                run_as_non_root=True,
                run_as_user=1000,
                fs_group=1000
            )
        )
        
        # 添加镜像拉取密钥
        image_pull_secret = self.cfg.get("K8S_IMAGE_PULL_SECRET")
        if image_pull_secret:
            pod_spec.image_pull_secrets = [
                client.V1LocalObjectReference(name=image_pull_secret)
            ]
        
        # Job规范
        job_spec = client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=pod_spec
            ),
            backoff_limit=0,  # 不重试
            active_deadline_seconds=spec.time_limit,
            ttl_seconds_after_finished=3600  # 1小时后清理
        )
        
        # Job对象
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=f"autoscorer-{spec.job_id[:12]}",
                labels={
                    "app": "autoscorer",
                    "job-id": spec.job_id,
                    "task-type": spec.task_type
                }
            ),
            spec=job_spec
        )
        
        return job
    
    def _wait_for_job_completion(self, batch_v1, job_name: str, timeout: int = 1800):
        """等待Job完成(简化实现)"""
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                job = batch_v1.read_namespaced_job(
                    name=job_name,
                    namespace=self.namespace
                )
                
                if job.status.succeeded:
                    logger.info(f"Job {job_name} completed successfully")
                    return
                elif job.status.failed:
                    raise AutoscorerError(
                        code="K8S_JOB_FAILED",
                        message=f"Job {job_name} failed"
                    )
                
                time.sleep(5)  # 每5秒检查一次
                
            except Exception as e:
                logger.error(f"Error checking job status: {e}")
                time.sleep(5)
        
        # 超时
        raise AutoscorerError(
            code="K8S_JOB_TIMEOUT",
            message=f"Job {job_name} timed out after {timeout} seconds"
        )
