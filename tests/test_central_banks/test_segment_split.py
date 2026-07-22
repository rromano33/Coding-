import pytest

from emrates.central_banks.segment_split import split_segment_change


def test_two_meetings_split_65_35():
    result = split_segment_change(100.0, 2)
    assert result == pytest.approx([65.0, 35.0])
    assert sum(result) == pytest.approx(100.0)


def test_single_meeting_gets_everything():
    assert split_segment_change(100.0, 1) == pytest.approx([100.0])


def test_three_meetings_first_gets_65_rest_split_evenly():
    result = split_segment_change(100.0, 3)
    assert result == pytest.approx([65.0, 17.5, 17.5])
    assert sum(result) == pytest.approx(100.0)


def test_zero_meetings_returns_empty():
    assert split_segment_change(100.0, 0) == []


def test_custom_first_weight():
    result = split_segment_change(100.0, 2, first_weight=0.5)
    assert result == pytest.approx([50.0, 50.0])


def test_negative_change_splits_the_same_way():
    result = split_segment_change(-80.0, 2)
    assert result == pytest.approx([-52.0, -28.0])
