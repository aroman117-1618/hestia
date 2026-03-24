"""
Variable interpolation for workflow node configs.

Resolves {{node_id.field.path}} references against prior node results.
Sandboxed: only resolves from the results dict, never external input.
"""

import json
import re
from typing import Any, Dict

INTERPOLATION_RE = re.compile(r"\{\{(\w+(?:\.\w+)*)\}\}")


def _resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve a dot-path like 'nodeA.response.content' against nested dicts."""
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def interpolate_config(config: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace {{node_id.field}} references in config with values from results.

    - Only resolves from the results dict (populated by prior node outputs)
    - Unresolved references are left intact (safe default)
    - Works recursively on nested dicts
    """
    serialized = json.dumps(config)

    def replacer(match: re.Match) -> str:
        path = match.group(1)
        value = _resolve_path(results, path)
        if value is None:
            return match.group(0)  # Leave unresolved
        if isinstance(value, str):
            return value
        return str(value)

    interpolated = INTERPOLATION_RE.sub(replacer, serialized)
    return json.loads(interpolated)
