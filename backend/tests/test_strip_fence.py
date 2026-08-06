"""测试 _strip_markdown_fence — 各种 LLM 输出格式。"""
import pytest
from app.llm_client import _strip_markdown_fence


def test_no_fence():
    assert _strip_markdown_fence('{"tool": "search"}') == '{"tool": "search"}'


def test_json_fence():
    result = _strip_markdown_fence('```json\n{"tool": "search"}\n```')
    assert result == '{"tool": "search"}'


def test_html_fence():
    result = _strip_markdown_fence('```html\n<div>hello</div>\n```')
    assert result == '<div>hello</div>'


def test_python_fence():
    result = _strip_markdown_fence('```python\nprint(1)\n```')
    assert result == 'print(1)'


def test_generic_fence():
    result = _strip_markdown_fence('```\nsome text\n```')
    assert result == 'some text'


def test_only_opening_fence():
    result = _strip_markdown_fence('```json\n{"a": 1}')
    assert result == '{"a": 1}'


def test_only_closing_fence():
    result = _strip_markdown_fence('{"a": 1}\n```')
    assert result == '{"a": 1}'


def test_empty_string():
    assert _strip_markdown_fence("") == ""
