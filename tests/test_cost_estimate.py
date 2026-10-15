import pytest

from core import costs


def test_estimate_range_for_opus(tmp_path):
    e = costs.estimate_report_cost("claude-opus-5-5", "x", counted_tokens=40000, output_tokens=15000)
    first = 40000 / 1e6 * 4 + 15000 / 1e6 * 20               # 0.16 + 0.30
    corr = 55000 / 1e6 * 4 + 15000 / 1e6 * 20                # 0.22 + 0.30
    assert e["low_usd"] == pytest.approx(first) and e["high_usd"] == pytest.approx(first + 2 * corr)
    assert e["counted"] and e["known_price"]


def test_estimate_without_count_uses_prompt_length():
    e = costs.estimate_report_cost("claude-opus-5-5", "α" * 20000)
    assert e["input_tokens"] == 10000 and not e["counted"]


def test_history_learns_average(tmp_path):
    f = tmp_path / "c.json"
    assert costs.cost_history_summary(f) is None
    costs.record_report_cost(0.50, 1, 14000, f)
    costs.record_report_cost(1.50, 3, 16000, f)
    s = costs.cost_history_summary(f)
    assert s["n"] == 2 and s["avg_usd"] == pytest.approx(1.0) and s["avg_out"] == pytest.approx(15000)
