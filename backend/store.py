"""Small local JSON store. Prototype only; not suitable for concurrent production writes."""
from pathlib import Path
import json
from threading import RLock
from core import sample_claims

class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save({'claims': sample_claims(), 'reviews': []})
    def read(self):
        with self.lock:
            return json.loads(self.path.read_text(encoding='utf-8'))
    def save(self, data):
        with self.lock:
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
            temp.replace(self.path)
    def update(self, fn):
        with self.lock:
            data = self.read()
            result = fn(data)
            self.save(data)
            return result
