from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    """轻量级基于 SQLite 的任务结果持久化。

    表结构 tasks:
      - task_id TEXT PRIMARY KEY
      - action TEXT
      - workspace TEXT
      - state TEXT  # SUBMITTED|STARTED|SUCCESS|FAILURE|REVOKED|PENDING|RETRY
      - result_json TEXT  # 成功结果（JSON）
      - error_json TEXT   # 失败信息（JSON）
      - created_at TEXT   # ISO8601
      - updated_at TEXT   # ISO8601
      - finished_at TEXT  # ISO8601
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def from_config(cls, cfg: Optional[Any] = None) -> "TaskStore":
        """根据配置创建 TaskStore，默认路径 logs/task_results.db"""
        base = Path.cwd()
        try:
            # 尝试项目根（src/../../）
            base = Path(__file__).resolve().parents[3]
        except Exception:
            pass
        default_path = base / "logs" / "task_results.db"
        db_path = None
        if cfg is not None:
            try:
                db_path = cfg.get("TASK_DB_PATH", str(default_path))
            except Exception:
                db_path = str(default_path)
        else:
            db_path = str(default_path)
        return cls(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)  # autocommit
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    action TEXT,
                    workspace TEXT,
                    state TEXT,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    finished_at TEXT
                )
                """
            )

    def upsert(
        self,
        task_id: str,
        *,
        action: Optional[str] = None,
        workspace: Optional[str] = None,
        state: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        finished: bool = False,
    ) -> None:
        now = _utc_now_iso()
        result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
        error_json = json.dumps(error, ensure_ascii=False) if error is not None else None
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT task_id FROM tasks WHERE task_id=?", (task_id,))
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(
                    """
                    INSERT INTO tasks (task_id, action, workspace, state, result_json, error_json, created_at, updated_at, finished_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        action,
                        workspace,
                        state,
                        result_json,
                        error_json,
                        now,
                        now,
                        now if finished else None,
                    ),
                )
            else:
                # 构建动态更新
                fields = []
                values = []
                if action is not None:
                    fields.append("action=?")
                    values.append(action)
                if workspace is not None:
                    fields.append("workspace=?")
                    values.append(workspace)
                if state is not None:
                    fields.append("state=?")
                    values.append(state)
                if result is not None:
                    fields.append("result_json=?")
                    values.append(result_json)
                if error is not None:
                    fields.append("error_json=?")
                    values.append(error_json)
                if finished:
                    fields.append("finished_at=?")
                    values.append(now)
                fields.append("updated_at=?")
                values.append(now)
                values.append(task_id)
                sql = f"UPDATE tasks SET {', '.join(fields)} WHERE task_id=?"
                cur.execute(sql, tuple(values))

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT task_id, action, workspace, state, result_json, error_json, created_at, updated_at, finished_at FROM tasks WHERE task_id=?",
                (task_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            result_json = row[4]
            error_json = row[5]
            return {
                "task_id": row[0],
                "action": row[1],
                "workspace": row[2],
                "state": row[3],
                "result": json.loads(result_json) if result_json else None,
                "error": json.loads(error_json) if error_json else None,
                "created_at": row[6],
                "updated_at": row[7],
                "finished_at": row[8],
            }
