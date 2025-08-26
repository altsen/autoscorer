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
# Ensure built-in scorers are registered via package import side-effect
from autoscorer import scorers as _builtin_scorers  # noqa: F401
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
# AutoScorer CLI Application
app = typer.Typer(
    name="autoscorer",
    help="AutoScorer - 自动化评分系统",
    rich_markup_mode="rich",
    no_args_is_help=True
)

@app.command()
def submit(workspace: str, 
           action: str = typer.Option("run", help="执行动作: run|score|pipeline"), 
           params: Optional[str] = typer.Option(None, help="JSON字符串，评分器参数")):
    """提交异步任务到 Celery 队列"""
    try:
        ws = Path(workspace)
        if not ws.exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "validation", {"workspace": str(ws)}))
            return
            
        # 解析参数
        try:
            p = json.loads(params) if params else {}
        except json.JSONDecodeError as e:
            print(make_cli_error("INVALID_PARAMS", f"Invalid JSON params: {str(e)}", "validation", {"params": params}))
            return
            
        # 动态导入 celery_app.tasks
        spec = importlib.util.spec_from_file_location(
            "celery_tasks",
            str(Path(__file__).parent.parent.parent / "celery_app" / "tasks.py"))
        celery_tasks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(celery_tasks)
        
        task_name_map = {
            "run": "autoscorer.run_job",
            "score": "autoscorer.score_job",
            "pipeline": "autoscorer.run_and_score_job",
        }
        if action not in task_name_map:
            print(make_cli_error("INVALID_ACTION", f"Invalid action '{action}'. Use: run|score|pipeline", "validation"))
            return
        task_name = task_name_map[action]
        args_map = {
            "autoscorer.run_job": (str(ws), None, None),
            "autoscorer.score_job": (str(ws), p, None, None),
            "autoscorer.run_and_score_job": (str(ws), p, None, None),
        }
        result = celery_tasks.celery_app.send_task(task_name, args=args_map[task_name])
        data = {"submitted": True, "task_id": result.id, "action": action, "params": p}
            
        print(make_cli_success(data, workspace=str(ws)))
        
    except Exception as e:
        print(make_cli_error("SUBMIT_ERROR", str(e), "async_submission", {"workspace": workspace}))


@app.command()
def validate(workspace: str):
    """验证工作区结构与 meta.json 配置文件"""
    try:
        ws = Path(workspace)
        if not ws.exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "validation", {"workspace": str(ws)}))
            return
            
        spec = JobSpec.from_workspace(ws)
        data = {
            "validated": True, 
            "job_id": spec.job_id, 
            "task_type": spec.task_type,
            "workspace_path": str(ws.resolve())
        }
        print(make_cli_success(data, workspace=str(ws)))
    except Exception as e:
        print(make_cli_error("VALIDATION_ERROR", str(e), "validation", {"workspace": workspace}))


@app.command()
def run(workspace: str, backend: str = typer.Option("docker", help="执行后端: docker|k8s|auto")):
    """执行推理容器，生成预测结果（不包含评分）"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        if not ws.exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "validation", {"workspace": str(ws)}))
            return
            
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
        print(make_cli_error(e.code, e.message, "execution", {"workspace": workspace}))
    except Exception as e:
        print(make_cli_error("RUN_ERROR", str(e), "execution", {"workspace": workspace}))


@app.command()
def score(workspace: str, 
          params: Optional[str] = typer.Option(None, help="JSON字符串，评分器参数"), 
          scorer: Optional[str] = typer.Option(None, help="指定使用的评分器名称")):
    """对现有预测结果进行评分并生成 result.json"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        if not ws.exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "validation", {"workspace": str(ws)}))
            return
            
        # 解析参数
        try:
            p: Dict = json.loads(params) if params else {}
        except json.JSONDecodeError as e:
            print(make_cli_error("INVALID_PARAMS", f"Invalid JSON params: {str(e)}", "validation", {"params": params}))
            return
        
        from autoscorer.pipeline import score_only
        result, output_path = score_only(ws, p, scorer_override=scorer)
        execution_time = time.time() - start_time
        
        # 标准化序列化（pydantic v2）
        payload = result.model_dump() if hasattr(result, 'model_dump') else (result.dict() if hasattr(result, 'dict') else result)
        data = {
            "score_result": payload,
            "output_path": str(output_path)
        }
        
        print(make_cli_success(
            data,
            execution_time=execution_time,
            workspace=str(ws),
            scorer_used=scorer or "auto"
        ))
        
    except AutoscorerError as e:
        print(make_cli_error(e.code, e.message, "scoring", {"workspace": workspace}))
    except Exception as e:
        print(make_cli_error("SCORE_ERROR", str(e), "scoring", {"workspace": workspace}))


@app.command()
def pipeline(workspace: str,
             backend: str = typer.Option("docker", help="执行后端: docker|k8s|auto"),
             params: Optional[str] = typer.Option(None, help="JSON字符串，评分器参数"),
             scorer: Optional[str] = typer.Option(None, help="指定使用的评分器名称")):
    """执行完整的推理+评分流水线"""
    start_time = time.time()
    try:
        ws = Path(workspace)
        if not ws.exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "validation", {"workspace": str(ws)}))
            return
            
        # 解析参数
        try:
            p: Dict = json.loads(params) if params else {}
        except json.JSONDecodeError as e:
            print(make_cli_error("INVALID_PARAMS", f"Invalid JSON params: {str(e)}", "validation", {"params": params}))
            return
        
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
        print(make_cli_error(e.code, e.message, "pipeline", {"workspace": workspace}))
    except Exception as e:
        print(make_cli_error("PIPELINE_ERROR", str(e), "pipeline", {"workspace": workspace}))


@app.command()
def scorers(action: str = typer.Argument(help="子命令: list|load|reload|test"), 
           file_path: Optional[str] = typer.Option(None, help="Python评分器文件路径"),
           scorer_name: Optional[str] = typer.Option(None, help="评分器名称"),
           workspace: Optional[str] = typer.Option(None, help="测试工作空间路径")):
    """评分器管理：列出、加载、重载和测试评分器"""
    from autoscorer.scorers.registry import (
        list_scorers, load_scorer_file, reload_scorer_file, 
        get_scorer_class, start_watching_file, get_watched_files
    )
    
    if action == "list":
        try:
            scorers = list_scorers()
            watched = get_watched_files()
            data = {
                "scorers": scorers,
                "total": len(scorers),
                "watched_files": watched
            }
            print(make_cli_success(data, action="scorers_list"))
        except Exception as e:
            print(make_cli_error("LIST_ERROR", str(e), "scorers"))
    
    elif action == "load":
        if not file_path:
            print(make_cli_error("MISSING_ARGUMENT", "file_path is required for load action", "scorers"))
            return
        if not Path(file_path).exists():
            print(make_cli_error("FILE_NOT_FOUND", f"File not found: {file_path}", "scorers", {"file_path": file_path}))
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
            print(make_cli_error("LOAD_ERROR", str(e), "scorers", {"file_path": file_path}))
    
    elif action == "reload":
        if not file_path:
            print(make_cli_error("MISSING_ARGUMENT", "file_path is required for reload action", "scorers"))
            return
        if not Path(file_path).exists():
            print(make_cli_error("FILE_NOT_FOUND", f"File not found: {file_path}", "scorers", {"file_path": file_path}))
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
            print(make_cli_error("RELOAD_ERROR", str(e), "scorers", {"file_path": file_path}))
    
    elif action == "test":
        if not scorer_name or not workspace:
            print(make_cli_error("MISSING_ARGUMENT", "scorer_name and workspace are required for test action", "scorers"))
            return
        if not Path(workspace).exists():
            print(make_cli_error("WORKSPACE_NOT_FOUND", f"Workspace not found: {workspace}", "scorers", {"workspace": workspace}))
            return
        try:
            scorer_cls = get_scorer_class(scorer_name)
            if scorer_cls is None:
                available = list(list_scorers().keys())
                print(make_cli_error("SCORER_NOT_FOUND", f"Scorer '{scorer_name}' not found", "scorers", {"available": available}))
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
            print(make_cli_error("TEST_ERROR", str(e), "scorers", {"scorer": scorer_name, "workspace": workspace}))
    
    else:
        print(make_cli_error("INVALID_ACTION", f"Unknown action: {action}. Use: list|load|reload|test", "scorers"))


@app.command()
def config(action: str = typer.Argument(help="子命令: show|validate|dump|paths"), 
          config_path: Optional[str] = typer.Option(None, help="自定义配置文件路径")):
    """配置管理：显示、验证和导出配置"""
    try:
        from autoscorer.utils.config import Config, get_config_search_paths, find_config_file
        
        if action == "paths":
            # 显示配置文件搜索路径
            search_paths = get_config_search_paths()
            current_config = find_config_file()
            
            paths_info = {
                "search_paths": search_paths,
                "current_config": current_config,
                "search_order": [
                    "1. 当前工作目录",
                    "2. 项目根目录", 
                    "3. 用户主目录 (~/.autoscorer/)",
                    "4. 系统配置目录 (/etc/autoscorer/)"
                ]
            }
            print(make_cli_success(paths_info))
            return
        
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
            
            print(make_cli_success(config_data, config_file=cfg.get_config_path()))
            
        elif action == "validate":
            # 验证配置
            errors = cfg.validate()
            if errors:
                print(make_cli_error("CONFIG_VALIDATION_ERROR", 
                                   f"Found {len(errors)} configuration errors", 
                                   "config_management",
                                   {"errors": errors}))
            else:
                print(make_cli_success({"validation": "passed"}, config_file=cfg.get_config_path()))
                
        elif action == "dump":
            # 导出配置（隐藏敏感信息）
            config_dump = cfg.dump()
            print(make_cli_success(config_dump, config_file=cfg.get_config_path()))
            
        else:
            print(make_cli_error("INVALID_ACTION", f"Unknown action: {action}. Use: show|validate|dump|paths", "config_management"))
            
    except Exception as e:
        print(make_cli_error("CONFIG_ERROR", str(e), "config_management", {"config_path": config_path}))


if __name__ == "__main__":
    app()

