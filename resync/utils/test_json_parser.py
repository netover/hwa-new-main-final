import pytest

from ..exceptions import ParsingError
from .json_parser import parse_llm_json_response


def test_parse_llm_json_success():
    """Tests successful parsing of a valid JSON string with required keys."""
    text = 'Some leading text {"key1": "value1", "key2": 123} and some trailing text.'
    required_keys = ["key1", "key2"]
    expected = {"key1": "value1", "key2": 123}
    assert parse_llm_json_response(text, required_keys) == expected


def test_parse_llm_json_raises_parsing_error_on_missing_keys():
    """Tests that ParsingError is raised when required keys are missing."""
    text = '{"key1": "value1"}'
    required_keys = ["key1", "key2"]
    with pytest.raises(ParsingError) as excinfo:
        parse_llm_json_response(text, required_keys)
    assert "missing required keys: key2" in str(excinfo.value)


def test_parse_llm_json_raises_parsing_error_on_malformed_json():
    """Tests that ParsingError is raised for malformed JSON."""
    text = '{"key1": "value1", '  # Missing closing brace and value
    required_keys = ["key1"]
    with pytest.raises(ParsingError) as excinfo:
        parse_llm_json_response(text, required_keys)
    assert "Invalid JSON format" in str(excinfo.value)


def test_parse_llm_json_raises_parsing_error_on_no_json_object():
    """Tests that ParsingError is raised when no JSON object is found."""
    text = "This is just a plain string without any JSON."
    required_keys = ["key"]
    with pytest.raises(ParsingError) as excinfo:
        parse_llm_json_response(text, required_keys)
    assert "No valid JSON object found" in str(excinfo.value)
