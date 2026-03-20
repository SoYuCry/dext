from decimal import Decimal
import pytest

from exchanges.variational import parse_indicative_quote


def test_parse_indicative_quote_ok():
    qid, bid, ask = parse_indicative_quote({"quote_id": "abc", "bid": "123.45", "ask": "123.55"})
    assert qid == "abc"
    assert bid == Decimal("123.45")
    assert ask == Decimal("123.55")


def test_parse_indicative_quote_missing_fields():
    with pytest.raises(ValueError):
        parse_indicative_quote({"quote_id": "abc", "bid": "1"})
