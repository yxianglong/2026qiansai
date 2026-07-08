import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class HistoryStore:
    def __init__(self, path: str = "data/history.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict) -> None:
        payload = dict(record)
        payload.setdefault("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load(self, limit: int = 500) -> List[Dict]:
        if not self.path.exists():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-limit:]
