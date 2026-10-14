from core import eta


def test_uses_configured_range_until_three_runs(tmp_path, monkeypatch):
    f = tmp_path / "d.json"
    monkeypatch.setenv("AUTO_ETA_MINUTES", "20-35")
    assert eta.typical_range(f) == (20, 35)
    eta.record_duration(4, f); eta.record_duration(6, f)
    assert eta.typical_range(f) == (20, 35)


def test_learns_from_real_durations(tmp_path):
    f = tmp_path / "d.json"
    for m in (4, 5, 6, 7, 30):
        eta.record_duration(m, f)
    lo, hi = eta.typical_range(f)
    assert lo == 5 and hi == 7          # το ακραίο 30 δεν τραβά την εκτίμηση


def test_remaining_never_negative(tmp_path):
    f = tmp_path / "d.json"
    for m in (4, 5, 6):
        eta.record_duration(m, f)
    assert eta.remaining_minutes(100, f) == (0, 1)
