import math
import statistics
from collections import Counter
import re
from typing import Optional


def calculate_cv(data):
    """Calculates Coefficient of Variation (std / mean)."""
    if len(data) < 2:
        return 0.0
    mean = statistics.mean(data)
    if mean == 0:
        return 0.0  # Avoid division by zero
    std = statistics.stdev(data)
    return std / mean


def calculate_entropy(data):
    """Calculates Shannon entropy for a list of discrete items (e.g., branch tags)."""
    if not data:
        return 0.0

    counts = Counter(data)
    total_count = len(data)
    entropy = 0.0

    for count in counts.values():
        probability = count / total_count
        entropy -= probability * math.log2(probability)

    return entropy


def normalize_score(value, min_val=0.0, max_val=1.0):
    """Clamps a value between min_val and max_val."""
    return max(min_val, min(value, max_val))


def exponential_decay_score(metric, alpha):
    """
    Maps a metric (where 0 is best) to a score [0, 1] using exponential decay.
    score = exp(-alpha * metric)
    """
    return math.exp(-alpha * metric)


def parse_time_string(time_str: Optional[str]) -> Optional[float]:
    """
    Parses a human-readable time string (e.g., "5s", "2m", "1.5h", "1d", "1w") into seconds.
    Raises ValueError for invalid formats.
    """
    if (
        time_str is None or time_str.lower().strip() == "none"
    ):  # Handle "None" string from CLI
        return None

    time_str = time_str.lower().strip()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([smhdw])", time_str)
    if not match:
        raise ValueError(
            f"Invalid time string format: {time_str}. Expected format like '5s', '2m', '1.5h', '1d'."
        )

    value = float(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    elif unit == "w":
        return value * 604800
    else:
        # This branch should ideally not be reached due to regex
        raise ValueError(f"Unknown time unit: {unit}")
