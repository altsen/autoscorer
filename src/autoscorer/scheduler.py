from autoscorer.utils.config import Config
from autoscorer.executor.docker_executor import DockerExecutor
from autoscorer.utils.errors import AutoscorerError
from autoscorer.utils.logger import get_logger

logger = get_logger("scheduler")

class Scheduler:
    def __init__(self, config_path: str = "config.yaml"):
        self.cfg = Config(config_path)
        self.use_k8s = self.cfg.get("K8S_ENABLED", False)
        self.nodes = self.cfg.get("NODES", [])
        # 允许通过 DOCKER_HOST 强制使用特定守护进程；当存在时不再选择 NODES
        self.docker_host = self.cfg.get("DOCKER_HOST")
        # 允许通过标志显式启用/禁用基于 NODES 的调度（默认禁用，除非你真的配置使用它）
        self.enable_nodes = self.cfg.get("DOCKER_NODES_ENABLED", False)
        logger.info(f"Scheduler initialized with K8S_ENABLED={self.use_k8s}")

    def select_executor(self):
        """选择执行器，优先Docker，K8s为可选项"""
        try:
            if self.use_k8s:
                # 尝试初始化K8s执行器
                try:
                    from autoscorer.executor.k8s_executor import K8sExecutor
                    logger.info("Using K8s executor")
                    return K8sExecutor()
                except ImportError as e:
                    logger.warning(f"K8s executor not available: {e}, falling back to Docker")
                except Exception as e:
                    logger.warning(f"K8s executor initialization failed: {e}, falling back to Docker")
            
            # 使用Docker执行器：优先 DOCKER_HOST（环境/配置），其次可选 NODES 策略，最后本机 docker.sock
            if self.docker_host:
                logger.info(f"Using configured DOCKER_HOST: {self.docker_host}")
                return DockerExecutor(node_host=self.docker_host)

            node = None
            if self.enable_nodes and (self.nodes or []):
                # 简单的节点选择策略：优先有GPU的节点
                nodes = sorted(self.nodes, key=lambda n: n.get("gpus", 0), reverse=True)
                node = nodes[0].get("host")
                logger.info(f"Selected Docker node from NODES: {node}")
                return DockerExecutor(node_host=node)

            logger.info("Using local Docker daemon (unix:///var/run/docker.sock)")
            return DockerExecutor()
            
        except Exception as e:
            logger.error(f"Failed to select executor: {e}")
            raise AutoscorerError(
                code="SCHEDULER_ERROR", 
                message=f"Failed to initialize executor: {e}"
            )

    def schedule(self, spec, workspace):
        """调度任务执行"""
        try:
            logger.info(f"Scheduling job {spec.job_id} with image {spec.container.image}")
            executor = self.select_executor()
            executor.run(spec, workspace)
            logger.info(f"Job {spec.job_id} completed successfully")
        except Exception as e:
            logger.error(f"Job {spec.job_id} failed: {e}")
            raise
