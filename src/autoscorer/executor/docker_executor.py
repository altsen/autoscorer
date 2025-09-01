from __future__ import annotations
from pathlib import Path
import os
from .base import Executor
from ..schemas.job import JobSpec
from autoscorer.utils.config import Config
import docker
from docker.types import DeviceRequest
import json
from autoscorer.utils.errors import AutoscorerError
from typing import Tuple, Optional
from autoscorer.utils.logger import get_logger

logger = get_logger("executor.docker")

class DockerExecutor(Executor):
    """支持远程API、配置化资源参数的docker执行器。"""

    def __init__(self, config_path: str = "config.yaml", node_host: str | None = None):
        self.cfg = Config(config_path)
        # 优先使用传入的 node_host，其次使用配置/环境中的 DOCKER_HOST，最后默认本机 docker.sock
        base_url = node_host or self.cfg.get("DOCKER_HOST") or "unix:///var/run/docker.sock"
        self.base_url = base_url
        self.client = docker.DockerClient(
            base_url=base_url,
            version=self.cfg.get("DOCKER_API_VERSION"),
            tls=self.cfg.get("DOCKER_TLS_VERIFY", False)
        )

    def run(self, spec: JobSpec, workspace: Path) -> None:
        ws = workspace.resolve()
        # 当通过 docker.sock 连接宿主 Docker 时，卷的 source 必须是“宿主机可见”的真实路径。
        # 这里将容器内路径（如 /app 或 /data/examples）映射回宿主机绝对路径。
        ws_str = str(ws)
        ws_host = ws
        try:
            base_is_local = isinstance(self.base_url, str) and self.base_url.startswith("unix://")
        except Exception:
            base_is_local = True

        if base_is_local:
            container_project = os.environ.get("CONTAINER_PROJECT_ROOT", "/app")
            host_project = os.environ.get("HOST_PROJECT_ROOT")
            container_examples = os.environ.get("CONTAINER_EXAMPLES_ROOT", "/data/examples")
            host_examples = os.environ.get("HOST_EXAMPLES_ROOT") or (
                (host_project and os.path.join(host_project, "examples")) or None
            )
            if host_project and ws_str.startswith(container_project + "/"):
                ws_host = Path(host_project + ws_str[len(container_project):]).resolve()
            elif host_examples and ws_str.startswith(container_examples + "/"):
                ws_host = Path(host_examples + ws_str[len(container_examples):]).resolve()
            # 如果传入的本就是宿主可见路径（/Users/... 或 /Volumes/...），保留原样
        
        # 用宿主机路径作为卷的 source
        input_dir = (ws_host / "input").resolve()
        output_dir = (ws_host / "output").resolve()
        logs_dir = (ws_host / "logs").resolve()
        logs_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 资源参数
        def _norm_mem(v: str | int | float | None, default: str = "4g") -> str:
            if v is None:
                s = str(default)
            else:
                s = str(v)
            s = s.strip()
            # 支持 Gi/Mi -> g/m，统一小写
            s = s.replace("Gi", "g").replace("GI", "g").replace("gi", "g")
            s = s.replace("Mi", "m").replace("MI", "m").replace("mi", "m")
            s = s.replace("G", "g").replace("M", "m")
            return s.lower()

        cpu = spec.resources.cpu or self.cfg.get("DEFAULT_CPU", 2)
        mem = _norm_mem(spec.resources.memory or self.cfg.get("DEFAULT_MEMORY", "4g"))
        gpus = spec.resources.gpus or self.cfg.get("DEFAULT_GPU", 0)
        shm_size = _norm_mem(spec.container.shm_size or self.cfg.get("DEFAULT_SHM_SIZE", "1g"), default="1g")
        timeout = spec.time_limit or self.cfg.get("TIMEOUT", 1800)

        # 环境变量
        env = spec.container.env or {}

        # 挂载
        mounts = [
            {"source": str(input_dir), "target": "/workspace/input", "type": "bind", "read_only": True},
            {"source": str(output_dir), "target": "/workspace/output", "type": "bind", "read_only": False},
            {"source": str((ws_host / "meta.json").resolve()), "target": "/workspace/meta.json", "type": "bind", "read_only": True},
        ]

        # 安全选项
        security_opts = self.cfg.get("SECURITY_OPTS", ["no-new-privileges:true"])

        # 网络策略：将自定义策略映射到 docker network_mode
        # none|host|bridge|<custom network name>
        policy = (spec.container.network_policy or "none").lower()
        if policy in {"none", "host", "bridge"}:
            network_mode = policy
        elif policy in {"restricted", "allowlist"}:
            # 简化处理：restricted -> none, allowlist -> bridge（可扩展到自定义网络）
            network_mode = "none" if policy == "restricted" else "bridge"
        else:
            # 允许用户直接提供自定义 docker 网络名
            network_mode = policy

        # 镜像仓库登录（可选）
        reg_user = self.cfg.get("REGISTRY_USER")
        reg_pass = self.cfg.get("REGISTRY_PASS")
        reg_url = self.cfg.get("REGISTRY_URL")
        try:
            if reg_user and reg_pass and reg_url:
                self.client.login(username=reg_user, password=reg_pass, registry=reg_url)
        except Exception:
            pass

        # 镜像解析与拉取策略
        pull_policy = str(self.cfg.get("IMAGE_PULL_POLICY", "ifnotpresent")).lower()
        image_present = False
        image_id = None
        action = "unknown"
        requested_ref = spec.container.image

        # 规范化镜像引用（补全 tag，优先使用 docker 的解析）
        def _parse_repo_tag(ref: str) -> Tuple[str, Optional[str]]:
            try:
                from docker.utils import utils as docker_utils  # type: ignore
                repo, tag = docker_utils.parse_repository_tag(ref)
                return repo, tag
            except Exception:
                # 回退：基于最后一个'/'之后的冒号切分，避免误伤 registry:port
                slash = ref.rfind('/')
                colon = ref.rfind(':')
                if colon > slash:
                    return ref[:colon], ref[colon + 1:]
                return ref, None

        repo, tag = _parse_repo_tag(requested_ref)
        normalized_ref = f"{repo}:{tag or 'latest'}"
        
        def _resolve_local_image() -> tuple[bool, Optional[str]]:
            # 优先直接 get（支持 id/name:tag）
            try:
                img0 = self.client.images.get(normalized_ref)
                return True, getattr(img0, 'id', None)
            except Exception:
                pass
            # 尝试 filters.reference 精确匹配
            try:
                lst = self.client.images.list(filters={"reference": normalized_ref})
                if lst:
                    return True, getattr(lst[0], 'id', None)
            except Exception:
                pass
            # 尝试按仓库名列出并比对 tags
            try:
                lst2 = self.client.images.list(name=repo)
                for im in lst2 or []:
                    for t in getattr(im, 'tags', []) or []:
                        if t == normalized_ref:
                            return True, getattr(im, 'id', None)
            except Exception:
                pass
            return False, None

        image_present, image_id = _resolve_local_image()
        if image_present:
            action = "use_local"
            logger.info(f"Found local image: {normalized_ref} -> {image_id}")
        else:
            logger.info(f"Image not found locally: {normalized_ref}")

        def _try_load_local_image() -> bool:
            nonlocal image_id, image_present
            # 支持在工作目录放置 image.tar(.gz/.tgz) 离线导入
            for name in ("image.tar", "image.tar.gz", "image.tgz"):
                p = ws / name
                if p.exists():
                    try:
                        logger.info(f"Loading local image from {name}")
                        data = p.read_bytes()
                        self.client.images.load(data)
                        try:
                            img2 = self.client.images.get(normalized_ref)
                            image_id = getattr(img2, 'id', None)
                            image_present = True
                        except Exception:
                            image_present = True  # 已加载但未能解析ID
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to load {name}: {e}")
            return False

        # 镜像拉取逻辑，增加重试机制
        max_retries = 3
        
        # 决定是否需要拉取镜像
        should_pull = False
        if pull_policy == "always":
            should_pull = True
            logger.info("Image pull strategy: policy=always, will pull")
        elif pull_policy == "ifnotpresent" and not image_present:
            should_pull = True
            logger.info("Image pull strategy: policy=ifnotpresent, present=false, will pull")
        elif pull_policy == "ifnotpresent" and image_present:
            should_pull = False
            logger.info("Image pull strategy: policy=ifnotpresent, present=true, using local image")
        elif pull_policy == "never":
            should_pull = False
            logger.info("Image pull strategy: policy=never, will not pull")
        
        if should_pull:
            pull_success = False
            for attempt in range(max_retries):
                try:
                    logger.info(f"Pulling image {normalized_ref} (attempt {attempt + 1}/{max_retries})")
                    self.client.images.pull(normalized_ref)
                    try:
                        img = self.client.images.get(normalized_ref)
                        image_id = getattr(img, 'id', None)
                        image_present = True
                    except Exception:
                        pass
                    action = "pulled"
                    pull_success = True
                    logger.info(f"Successfully pulled image: {normalized_ref}")
                    break
                except Exception as e:
                    logger.warning(f"Pull attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # 最后一次拉取失败，尝试本地离线镜像
                        if _try_load_local_image():
                            action = "loaded_tar"
                            pull_success = True
                            logger.info("Loaded image from local tar file")
                        else:
                            # 如果之前检测到本地有镜像，使用本地镜像并警告
                            if image_present:
                                logger.warning("Failed to pull new image, using existing local image")
                                action = "use_local_fallback"
                                pull_success = True
                            else:
                                raise AutoscorerError(
                                    code="IMAGE_PULL_FAILED",
                                    message=f"failed to pull image {normalized_ref} after {max_retries} attempts: {e}",
                                    details={"policy": pull_policy, "attempts": max_retries, "last_error": str(e)}
                                )
                    else:
                        # 等待后重试
                        import time
                        time.sleep(2 ** attempt)  # 指数退避
            
            if not pull_success:
                raise AutoscorerError(
                    code="IMAGE_PULL_FAILED",
                    message=f"failed to pull image {normalized_ref}",
                    details={"policy": pull_policy}
                )
                
        if pull_policy == "never" and not image_present:
            # 不允许拉取且本地不存在时，尝试离线导入
            if _try_load_local_image():
                action = "loaded_tar"
            else:
                raise AutoscorerError(
                    code="IMAGE_NOT_PRESENT",
                    message=(
                        f"image '{normalized_ref}' not present locally and IMAGE_PULL_POLICY=never; "
                        f"please pre-pull it or place an image.tar in {ws}"
                    ),
                )

        # 记录镜像解析信息
        try:
            info_payload = {
                "image_requested": requested_ref,
                "image_resolved": normalized_ref,
                "image_present_local": image_present,
                "image_id": image_id,
                "pull_policy": pull_policy,
                "action": action,
                "docker_host": self.base_url,
            }
            (logs_dir / "run_info.json").write_text(json.dumps(info_payload, ensure_ascii=False, indent=2))
            logger.info(f"docker image: {normalized_ref} -> {image_id or 'unknown'} ({action})")
        except Exception:
            pass

        # 容器创建
        device_requests = None
        if gpus and int(gpus) > 0:
            device_requests = [DeviceRequest(count=int(gpus), capabilities=[["gpu"]])]
        labels = {"app": "autoscorer", "job_id": spec.job_id}

        try:
            container = self.client.containers.run(
                image=normalized_ref,
                command=spec.container.cmd or [],
                environment=env,
                volumes={m["source"]: {"bind": m["target"], "mode": "ro" if m["read_only"] else "rw"} for m in mounts},
                network_mode=network_mode,
                security_opt=security_opts,
                shm_size=shm_size,
                detach=True,
                mem_limit=mem,
                nano_cpus=int(float(cpu) * 1e9),
                device_requests=device_requests,
                read_only=True,
                labels=labels,
                working_dir="/workspace",
                name=f"autoscorer-{spec.job_id[:12]}"
            )
        except Exception as e:
            raise AutoscorerError(code="CONTAINER_CREATE_FAILED", message=str(e))
        else:
            try:
                result = container.wait(timeout=timeout)
            except Exception as e:
                # 检查是否是超时异常
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    raise AutoscorerError(code="TIMEOUT_ERROR", message=f"container execution timed out after {timeout} seconds")
                else:
                    raise AutoscorerError(code="CONTAINER_WAIT_FAILED", message=str(e))
    
            logs = container.logs(stdout=True, stderr=True).decode(errors="ignore")
            (logs_dir / "container.log").write_text(logs)
            if isinstance(result, dict):
                status = result.get("StatusCode", result.get("Status", 1))
            else:
                status = result

            if status != 0:
                info = container.attrs
                (logs_dir / "inspect.json").write_text(str(info))
                raise AutoscorerError(code="CONTAINER_EXIT_NONZERO", message=f"exit {status}")
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
