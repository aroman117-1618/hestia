import pytest
from hestia.workflows.interpolation import interpolate_config


class TestInterpolateConfig:
    def test_simple_substitution(self) -> None:
        config = {"prompt": "Summarize: {{nodeA.response}}"}
        results = {"nodeA": {"response": "The market rose 5%"}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Summarize: The market rose 5%"

    def test_nested_path(self) -> None:
        config = {"prompt": "Score: {{nodeA.metrics.score}}"}
        results = {"nodeA": {"metrics": {"score": 0.95}}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Score: 0.95"

    def test_unresolved_left_intact(self) -> None:
        config = {"prompt": "Value: {{missing.field}}"}
        results = {}
        out = interpolate_config(config, results)
        assert out["prompt"] == "Value: {{missing.field}}"

    def test_multiple_substitutions(self) -> None:
        config = {"prompt": "{{a.x}} and {{b.y}}"}
        results = {"a": {"x": "hello"}, "b": {"y": "world"}}
        out = interpolate_config(config, results)
        assert out["prompt"] == "hello and world"

    def test_numeric_value_stringified(self) -> None:
        config = {"threshold": "{{nodeA.count}}"}
        results = {"nodeA": {"count": 42}}
        out = interpolate_config(config, results)
        assert out["threshold"] == "42"

    def test_nested_config_dict(self) -> None:
        config = {"condition": {"field": "{{a.output}}", "value": 10}}
        results = {"a": {"output": "status"}}
        out = interpolate_config(config, results)
        assert out["condition"]["field"] == "status"

    def test_empty_results_no_crash(self) -> None:
        config = {"prompt": "Hello {{x.y}}"}
        out = interpolate_config(config, {})
        assert out["prompt"] == "Hello {{x.y}}"

    def test_no_templates_passthrough(self) -> None:
        config = {"prompt": "No templates here"}
        out = interpolate_config(config, {"a": {"b": "c"}})
        assert out["prompt"] == "No templates here"
