from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app.services.estabelecimento_hours_service import (
    DAY_KEYS,
    WEEKDAY_TO_KEY,
    build_day_slots,
    default_working_hours,
    get_barbeiro_working_hours,
    get_working_hours,
    get_working_window,
    is_within_working_hours,
    normalize_working_hours,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_est(horarios=None):
    return SimpleNamespace(horarios_funcionamento=horarios)


def _make_barbeiro(horarios=None):
    return SimpleNamespace(horarios_funcionamento=horarios)


def _full_schedule(inicio="08:00", fim="18:00", closed_day=None):
    return {
        key: {"ativo": key != closed_day, "inicio": inicio, "fim": fim}
        for key in DAY_KEYS
    }


# ── default_working_hours ─────────────────────────────────────────────────────

def test_default_working_hours_has_all_days():
    result = default_working_hours()
    assert set(result.keys()) == set(DAY_KEYS)


def test_default_working_hours_all_active():
    result = default_working_hours()
    for day in DAY_KEYS:
        assert result[day]["ativo"] is True
        assert "inicio" in result[day]
        assert "fim" in result[day]


# ── normalize_working_hours ───────────────────────────────────────────────────

def test_normalize_none_returns_default():
    result = normalize_working_hours(None)
    assert result == default_working_hours()


def test_normalize_non_dict_returns_default():
    result = normalize_working_hours("invalid")
    assert result == default_working_hours()


def test_normalize_partial_dict_keeps_defaults_for_missing_keys():
    raw = {"seg": {"ativo": False, "inicio": "09:00", "fim": "17:00"}}
    result = normalize_working_hours(raw)
    assert result["seg"]["ativo"] is False
    assert result["seg"]["inicio"] == "09:00"
    assert result["ter"]["ativo"] is True


def test_normalize_invalid_time_falls_back_to_default():
    raw = {"seg": {"ativo": True, "inicio": "not-a-time", "fim": "25:99"}}
    defaults = default_working_hours()
    result = normalize_working_hours(raw)
    assert result["seg"]["inicio"] == defaults["seg"]["inicio"]
    assert result["seg"]["fim"] == defaults["seg"]["fim"]


def test_normalize_with_fallback_uses_fallback_instead_of_defaults():
    fallback = {key: {"ativo": False, "inicio": "10:00", "fim": "16:00"} for key in DAY_KEYS}
    result = normalize_working_hours(None, fallback=fallback)
    for day in DAY_KEYS:
        assert result[day]["inicio"] == "10:00"


def test_normalize_missing_day_entry_keeps_fallback():
    fallback = {key: {"ativo": True, "inicio": "09:00", "fim": "17:00"} for key in DAY_KEYS}
    raw = {"seg": "not-a-dict"}
    result = normalize_working_hours(raw, fallback=fallback)
    assert result["seg"]["inicio"] == "09:00"


# ── get_working_hours ─────────────────────────────────────────────────────────

def test_get_working_hours_with_custom_schedule():
    horarios = _full_schedule("09:00", "17:00")
    est = _make_est(horarios)
    result = get_working_hours(est)
    assert result["seg"]["inicio"] == "09:00"


def test_get_working_hours_with_no_schedule_returns_default():
    est = _make_est(None)
    result = get_working_hours(est)
    assert result == default_working_hours()


# ── get_barbeiro_working_hours ────────────────────────────────────────────────

def test_get_barbeiro_working_hours_barbeiro_sem_horarios_usa_estabelecimento():
    est = _make_est(_full_schedule("08:00", "18:00"))
    barbeiro = _make_barbeiro(None)
    result = get_barbeiro_working_hours(est, barbeiro)
    assert result == get_working_hours(est)


def test_get_barbeiro_working_hours_barbeiro_com_horarios_customizados():
    est = _make_est(_full_schedule("08:00", "18:00"))
    barbeiro_horarios = _full_schedule("13:00", "18:00")
    barbeiro = _make_barbeiro(barbeiro_horarios)
    result = get_barbeiro_working_hours(est, barbeiro)
    assert result["seg"]["inicio"] == "13:00"


# ── get_working_window ────────────────────────────────────────────────────────

def _next_weekday(weekday: int) -> date:
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def test_get_working_window_returns_times_for_open_day():
    est = _make_est(_full_schedule("08:00", "18:00"))
    next_monday = _next_weekday(0)
    window = get_working_window(est, next_monday)
    assert window is not None
    start, end = window
    assert start == time(8, 0)
    assert end == time(18, 0)


def test_get_working_window_returns_none_for_closed_day():
    horarios = _full_schedule("08:00", "18:00", closed_day="dom")
    est = _make_est(horarios)
    next_sunday = _next_weekday(6)
    window = get_working_window(est, next_sunday)
    assert window is None


def test_get_working_window_returns_none_when_start_equals_end():
    horarios = {key: {"ativo": True, "inicio": "08:00", "fim": "08:00"} for key in DAY_KEYS}
    est = _make_est(horarios)
    next_monday = _next_weekday(0)
    window = get_working_window(est, next_monday)
    assert window is None


def test_get_working_window_with_barbeiro_intersects():
    est = _make_est(_full_schedule("08:00", "18:00"))
    barbeiro_horarios = _full_schedule("13:00", "18:00")
    barbeiro = _make_barbeiro(barbeiro_horarios)
    next_monday = _next_weekday(0)
    window = get_working_window(est, next_monday, barbeiro=barbeiro)
    assert window is not None
    start, end = window
    assert start == time(13, 0)
    assert end == time(18, 0)


def test_get_working_window_with_barbeiro_closed_returns_none():
    est = _make_est(_full_schedule("08:00", "18:00"))
    barbeiro_horarios = _full_schedule("13:00", "18:00", closed_day="seg")
    barbeiro = _make_barbeiro(barbeiro_horarios)
    next_monday = _next_weekday(0)
    window = get_working_window(est, next_monday, barbeiro=barbeiro)
    assert window is None


def test_get_working_window_no_overlap_returns_none():
    est = _make_est(_full_schedule("08:00", "12:00"))
    barbeiro_horarios = _full_schedule("13:00", "18:00")
    barbeiro = _make_barbeiro(barbeiro_horarios)
    next_monday = _next_weekday(0)
    window = get_working_window(est, next_monday, barbeiro=barbeiro)
    assert window is None


# ── build_day_slots ───────────────────────────────────────────────────────────

def test_build_day_slots_returns_list_of_datetimes():
    est = _make_est(_full_schedule("08:00", "10:00"))
    next_monday = _next_weekday(0)
    slots = build_day_slots(est, next_monday, duration_minutes=30)
    assert isinstance(slots, list)
    assert all(isinstance(s, datetime) for s in slots)


def test_build_day_slots_empty_for_closed_day():
    horarios = _full_schedule("08:00", "18:00", closed_day="dom")
    est = _make_est(horarios)
    next_sunday = _next_weekday(6)
    slots = build_day_slots(est, next_sunday, duration_minutes=30)
    assert slots == []


def test_build_day_slots_count_matches_window():
    est = _make_est(_full_schedule("08:00", "10:00"))
    next_monday = _next_weekday(0)
    slots = build_day_slots(est, next_monday, duration_minutes=30)
    assert len(slots) > 0
    first = slots[0]
    assert first.hour == 8
    assert first.minute == 0


def test_build_day_slots_duration_longer_than_window_returns_empty():
    est = _make_est(_full_schedule("08:00", "08:30"))
    next_monday = _next_weekday(0)
    slots = build_day_slots(est, next_monday, duration_minutes=60)
    assert slots == []


# ── is_within_working_hours ───────────────────────────────────────────────────

def test_is_within_working_hours_true_for_valid_slot():
    est = _make_est(_full_schedule("08:00", "18:00"))
    next_monday = _next_weekday(0)
    start_at = datetime.combine(next_monday, time(9, 0))
    end_at = datetime.combine(next_monday, time(9, 30))
    assert is_within_working_hours(est, start_at, end_at) is True


def test_is_within_working_hours_false_for_before_opening():
    est = _make_est(_full_schedule("08:00", "18:00"))
    next_monday = _next_weekday(0)
    start_at = datetime.combine(next_monday, time(7, 0))
    end_at = datetime.combine(next_monday, time(7, 30))
    assert is_within_working_hours(est, start_at, end_at) is False


def test_is_within_working_hours_false_for_after_closing():
    est = _make_est(_full_schedule("08:00", "18:00"))
    next_monday = _next_weekday(0)
    start_at = datetime.combine(next_monday, time(17, 45))
    end_at = datetime.combine(next_monday, time(18, 30))
    assert is_within_working_hours(est, start_at, end_at) is False


def test_is_within_working_hours_false_for_closed_day():
    horarios = _full_schedule("08:00", "18:00", closed_day="dom")
    est = _make_est(horarios)
    next_sunday = _next_weekday(6)
    start_at = datetime.combine(next_sunday, time(9, 0))
    end_at = datetime.combine(next_sunday, time(9, 30))
    assert is_within_working_hours(est, start_at, end_at) is False


def test_is_within_working_hours_false_for_different_dates():
    est = _make_est(_full_schedule("08:00", "18:00"))
    next_monday = _next_weekday(0)
    next_tuesday = next_monday + timedelta(days=1)
    start_at = datetime.combine(next_monday, time(9, 0))
    end_at = datetime.combine(next_tuesday, time(9, 30))
    assert is_within_working_hours(est, start_at, end_at) is False
