import json
import os
import time
from typing import Dict
import atexit
import sys

STATE_FILE = ".pypss_alert_state.json"
_state_instance = None  # Singleton instance (optional, for explicit global access)


class AlertState:
    def __init__(self: "AlertState") -> None:
        self.state: Dict[str, float] = {}
        self._load()
        # Register save on exit to debounce writes
        if "pytest" not in sys.modules:  # Only register atexit if not in test
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
            # Ensure directory exists if STATE_FILE is in a path
            output_dir = os.path.dirname(STATE_FILE)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f)
        except Exception as e:
            # Print to stderr as logging might not be configured at exit
            print(f"⚠️ Failed to save alert state to {STATE_FILE}: {e}", file=sys.stderr)

    def should_alert(self, rule_name: str, cooldown_seconds: int = 3600) -> bool:
        last_time = self.state.get(rule_name, 0)
        if time.time() - last_time > cooldown_seconds:
            return True
        return False

    def record_alert(self, rule_name: str):
        self.state[rule_name] = time.time()
        # self.save() # NO: Now saving is debounced via atexit.
