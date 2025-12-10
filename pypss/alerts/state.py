import atexit
import json
import os
import sys
import time
from typing import Dict

STATE_FILE = ".pypss_alert_state.json"
_state_instance = None


class AlertState:
    def __init__(self: "AlertState") -> None:
        self.state: Dict[str, float] = {}
        self._load()
        if "pytest" not in sys.modules:
            atexit.register(self.save)

    def _load(self) -> None:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}

    def save(self) -> None:
        try:
            output_dir = os.path.dirname(STATE_FILE)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f)
        except Exception as e:
            print(f"⚠️ Failed to save alert state to {STATE_FILE}: {e}", file=sys.stderr)

    def should_alert(self, rule_name: str, cooldown_seconds: int = 3600) -> bool:
        last_time = self.state.get(rule_name, 0)
        if time.time() - last_time > cooldown_seconds:
            return True
        return False

    def record_alert(self, rule_name: str):
        self.state[rule_name] = time.time()
