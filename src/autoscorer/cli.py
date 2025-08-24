from pathlib import Path
from typing import Optional, Dict, Any
import json
import typer
from rich import print
from datetime import datetime, timezone
import time

from autoscorer.schemas.job import JobSpec
from autoscorer.schemas.result import Result
from autoscorer.executor.docker_executor import DockerExecutor
from autoscorer.scheduler import Scheduler
from autoscorer.scorers.registry import get_scorer
from autoscorer.utils.errors import make_error, AutoscorerError
from autoscorer.pipeline import run_and_score as pipeline_run_and_score


def make_cli_success(data: Any, execution_time: Optional[float] = None, **kwargs) -> Dict:
    """创建CLI标准化成功输出"""
    result = {
        "status": "success",
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if execution_time is not None:
        result["execution_time"] = execution_time
    result.update(kwargs)
    return result


def make_cli_error(code: str, message: str, stage: str = "cli", details: Optional[Dict] = None, **kwargs) -> Dict:
    """创建CLI标准化错误输出"""
    payload = {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "stage": stage
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if details is not None:
        payload["error"]["details"] = details
    if kwargs:
        payload.update(kwargs)
    return payload


import importlib.util
app = typer.Typer(help="autoscorer CLI")

@app.command()
def submit(workspace: str, action: str = typer.Option("run", help="run|score|pipeline"), params: Optional[str] = None):
    """提交任务到 Celery 队列（run 或 score）。"""
    try:
        ws = Path(workspace)
        # 动态导入 celery_app.tasks
        spec = importlib.util.spec_from_file_location(
            "celery_tasks",
            str(Path(__file__).parent.parent.parent / "celery_app" / "tasks.py"))
        celery_tasks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(celery_tasks)
        
        if action == "run":
            result = celery_tasks.run_job.delay(str(ws))
            data = {"submitted": True, "task_id": result.id, "action": "run"}
        elif action == "score":
            p = json.loads(params) if params else {}
            result = celery_tasks.score_job.delay(str(ws), p)
            data = {"submitted": True, "task_id": result.id, "action": "score", "params": p}
        elif action == "pipeline":
            p = json.loads(params) if params else {}
            result = celery_tasks.run_and_score_job.delay(str(ws), p)
            data = {"submitted": True, "task_id": result.id, "action": "pipeline", "params": p}
        else:
            print(make_cli_error("INVALID_ACTION", "action must be run, score, or pipeline"))
            return
            
        print(make_cli_success(data, workspace=str(ws)))
        
    except Exception as e:
        print(make_cli_error("SUBMIT_ERROR", str(e)))


@app.command()
def validate(workspace: str):
    """校验标准工作区结构与 meta.json。"""
    try:
        ws = Path(workspace)
        spec = JobSpec.from_workspace(ws)
        data = {"validated": True, "job_id": spec.job_id, "task_type": spec.task_type}
        print(make_cli_success(data, workspace=str(ws)))
    except Exception as e:
        print(make_cli_error("VALIDATION_ERROR", str(e), "validation"))


@app.command()
def run(workspace: str, backend: str = typer.Option("docker", help="docker|k8s|auto")):
    """运行选手镜像完成推理阶段（仅执行容器，不评分）。"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        from autoscorer.pipeline import run_only
        
        result = run_only(ws, backend)
        execution_time = time.time() - start_time
        
        data = {"run_result": result}
        print(make_cli_success(
            data, 
            execution_time=execution_time,
            workspace=str(ws),
            backend_used=backend
        ))
        
    except AutoscorerError as e:
        print(make_cli_error(e.code, e.message, "execution"))
    except Exception as e:
        print(make_cli_error("RUN_ERROR", str(e), "execution"))


@app.command()
def score(workspace: str, params: Optional[str] = typer.Option(None, help="JSON字符串，传入给评分器"), scorer: Optional[str] = typer.Option(None, help="指定使用的scorer")):
    """对 output 下的预测结果进行评分并生成 result.json。"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        p: Dict = json.loads(params) if params else {}
        
        from autoscorer.pipeline import score_only
        result, output_path = score_only(ws, p, scorer_override=scorer)
        execution_time = time.time() - start_time
        
        data = {
            "score_result": result.dict() if hasattr(result, 'dict') else result,
            "output_path": str(output_path)
        }
        
        print(make_cli_success(
            data,
            execution_time=execution_time,
            workspace=str(ws),
            scorer_used=scorer or "auto"
        ))
        
    except AutoscorerError as e:
        print(make_cli_error(e.code, e.message, "scoring"))
    except Exception as e:
        print(make_cli_error("SCORE_ERROR", str(e), "scoring"))


@app.command()
def pipeline(workspace: str,
             backend: str = typer.Option("docker", help="docker|k8s|auto"),
             params: Optional[str] = typer.Option(None, help="JSON字符串，传入给评分器"),
             scorer: Optional[str] = typer.Option(None, help="指定使用的scorer")):
    """运行推理并在成功后立即执行评分（同步流水线）。"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        p: Dict = json.loads(params) if params else {}
        
        result = pipeline_run_and_score(ws, p, backend, scorer_override=scorer)
        execution_time = time.time() - start_time
        
        data = {"pipeline_result": result}
        
        print(make_cli_success(
            data,
            execution_time=execution_time,
            workspace=str(ws),
            backend_used=backend,
            scorer_used=scorer or "auto"
        ))
        
    except AutoscorerError as e:
        print(make_cli_error(e.code, e.message, "pipeline"))
    except Exception as e:
        print(make_cli_error("PIPELINE_ERROR", str(e), "pipeline"))


@app.command()
def scorers(action: str = typer.Argument(help="list|load|reload|test"), 
           file_path: Optional[str] = typer.Option(None, help="Python文件路径"),
           scorer_name: Optional[str] = typer.Option(None, help="Scorer名称"),
           workspace: Optional[str] = typer.Option(None, help="测试工作空间")):
    """管理scorer: list(列出), load(加载), reload(重载), test(测试)"""
    from autoscorer.scorers.registry import (
        list_scorers, load_scorer_file, reload_scorer_file, 
        get_scorer_class, start_watching_file, get_watched_files
    )
    
    if action == "list":
        scorers = list_scorers()
        watched = get_watched_files()
        data = {
            "scorers": scorers,
            "total": len(scorers),
            "watched_files": watched
        }
        print(make_cli_success(data, action="scorers_list"))
    
    elif action == "load":
        if not file_path:
            print(make_cli_error("INVALID_ARGS", "file_path is required for load action", stage="scorers"))
            return
        try:
            loaded = load_scorer_file(file_path)
            # 自动启用监控
            start_watching_file(file_path)
            data = {
                "loaded": {name: cls.__name__ for name, cls in loaded.items()},
                "count": len(loaded),
                "watching": True,
                "file_path": file_path
            }
            print(make_cli_success(data, action="scorers_load"))
        except Exception as e:
            print(make_cli_error("LOAD_ERROR", str(e), stage="scorers", details={"file_path": file_path}))
    
    elif action == "reload":
        if not file_path:
            print(make_cli_error("INVALID_ARGS", "file_path is required for reload action", stage="scorers"))
            return
        try:
            loaded = reload_scorer_file(file_path)
            data = {
                "reloaded": {name: cls.__name__ for name, cls in loaded.items()},
                "count": len(loaded),
                "file_path": file_path
            }
            print(make_cli_success(data, action="scorers_reload"))
        except Exception as e:
            print(make_cli_error("RELOAD_ERROR", str(e), stage="scorers", details={"file_path": file_path}))
    
    elif action == "test":
        if not scorer_name or not workspace:
            print(make_cli_error("INVALID_ARGS", "scorer_name and workspace are required for test action", stage="scorers"))
            return
        try:
            scorer_cls = get_scorer_class(scorer_name)
            if scorer_cls is None:
                available = list(list_scorers().keys())
                print(make_cli_error("SCORER_NOT_FOUND", f"Scorer '{scorer_name}' not found", stage="scorers", details={"available": available}))
                return
            
            ws = Path(workspace)
            scorer = scorer_cls()
            result = scorer.score(ws, {})
            data = {
                "scorer": scorer_name,
                "class": scorer_cls.__name__,
                "result": {
                    "summary": result.summary,
                    "versioning": result.versioning
                }
            }
            print(make_cli_success(data, action="scorers_test", workspace=str(ws)))
        except Exception as e:
            print(make_cli_error("TEST_ERROR", str(e), stage="scorers", details={"scorer": scorer_name, "workspace": workspace}))
    
    else:
        print(make_cli_error("INVALID_ACTION", f"Unknown action: {action}. Use: list|load|reload|test", stage="scorers"))


@app.command()
def config(action: str = typer.Argument(help="show|validate|dump"), 
          config_path: Optional[str] = typer.Option(None, help="配置文件路径")):
    """配置管理: show(显示), validate(验证), dump(导出)"""
    try:
        from autoscorer.utils.config import Config
        
        cfg = Config(config_path) if config_path else Config()
        
        if action == "show":
            # 显示主要配置项
            key_configs = [
                "DOCKER_HOST", "IMAGE_PULL_POLICY", "DEFAULT_CPU", "DEFAULT_MEMORY", 
                "DEFAULT_GPU", "TIMEOUT", "K8S_ENABLED", "K8S_NAMESPACE",
                "CELERY_BROKER", "LOG_DIR", "WORKSPACE_ROOT"
            ]
            
            config_data = {}
            for key in key_configs:
                config_data[key] = cfg.get(key)
            
            print(make_cli_success(config_data, config_file=str(cfg.path)))
            
        elif action == "validate":
            # 验证配置
            errors = cfg.validate()
            if errors:
                print(make_cli_error("CONFIG_VALIDATION_ERROR", 
                                   f"Found {len(errors)} configuration errors", 
                                   details={"errors": errors}))
            else:
                print(make_cli_success({"validation": "passed"}, config_file=str(cfg.path)))
                
        elif action == "dump":
            # 导出配置（隐藏敏感信息）
            config_dump = cfg.dump()
            print(make_cli_success(config_dump, config_file=str(cfg.path)))
            
        else:
            print(make_cli_error("INVALID_ACTION", f"Unknown action: {action}. Use: show|validate|dump"))
            
    except Exception as e:
        print(make_cli_error("CONFIG_ERROR", str(e), "config_management"))


if __name__ == "__main__":
    app()

