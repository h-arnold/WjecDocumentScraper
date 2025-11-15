from __future__ import annotations


from src.llm.json_utils import parse_json_response


def test_parse_json_object_in_text():
    text = "Here is the result: {\"key\": \"value\"}. Thanks"
    result = parse_json_response(text)
    assert isinstance(result, dict)
    assert result["key"] == "value"


def test_parse_json_array_in_text():
    text = "Some preamble text [ {\"issue_id\": 1, \"error_category\": \"PARSING_ERROR\", \"confidence_score\": 90, \"reasoning\": \"Test\"} ] end"
    result = parse_json_response(text)
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["issue_id"] == 1
