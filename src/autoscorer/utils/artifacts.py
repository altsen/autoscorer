from pathlib import Path
import hashlib
from typing import Dict

class ArtifactManager:
    @staticmethod
    def file_info(p: Path) -> Dict:
        if not p.exists():
            return {}
        return {
            "path": str(p),
            "size": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }

    @staticmethod
    def collect_dir(d: Path, patterns=("*.json", "*.csv", "*.txt")) -> Dict[str, Dict]:
        result = {}
        if not d.exists():
            return result
        for pat in patterns:
            for f in d.rglob(pat):
                result[f.name] = ArtifactManager.file_info(f)
        return result
