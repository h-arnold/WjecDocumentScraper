from __future__ import annotations

from src.models import PassCode


def test_passcode_values() -> None:
    assert PassCode.LT.value == "LT"
    assert PassCode.LTC.value == "LTC"
    assert set(PassCode.all_values()) == {"LT", "LTC", "LCV", "LP"}
