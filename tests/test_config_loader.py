"""Unit tests for the config loader's env-var expansion."""

from app.config import _expand_env


def test_env_var_expansion(monkeypatch):
    monkeypatch.setenv("MY_VAR", "the-value")
    assert _expand_env("prefix-${MY_VAR}-suffix") == "prefix-the-value-suffix"


def test_missing_env_var_becomes_empty(monkeypatch):
    monkeypatch.delenv("UNDEFINED", raising=False)
    assert _expand_env("${UNDEFINED}") == ""


def test_nested_dict_expansion(monkeypatch):
    monkeypatch.setenv("T", "X")
    out = _expand_env({"admin": {"token": "${T}"}, "list": ["${T}", "lit"]})
    assert out == {"admin": {"token": "X"}, "list": ["X", "lit"]}


def test_non_string_passthrough():
    assert _expand_env(42) == 42
    assert _expand_env(True) is True
    assert _expand_env(None) is None


def test_only_uppercase_env_pattern_matches(monkeypatch):
    monkeypatch.setenv("lowercase_var", "should-not-match")
    monkeypatch.setenv("MY_TOKEN", "should-match")
    # lowercase pattern won't match the regex
    assert _expand_env("${lowercase_var}") == "${lowercase_var}"
    assert _expand_env("${MY_TOKEN}") == "should-match"
