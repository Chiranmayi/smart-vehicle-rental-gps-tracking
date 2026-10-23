
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.routers.bookings import _calculate_rental_price


def test_weekday_rental_price():
    # Monday to Tuesday: one weekday at ₹500 per day.
    start_date = date(2026, 11, 2)  # Monday
    end_date = date(2026, 11, 3)

    price = _calculate_rental_price(500, start_date, end_date)

    assert price == 500


def test_weekend_rental_price():
    # Saturday to Sunday: one weekend day at 20% extra.
    start_date = date(2026, 11, 7)  # Saturday
    end_date = date(2026, 11, 8)

    price = _calculate_rental_price(500, start_date, end_date)

    assert price == 600


def test_peak_season_rental_price():
    # December weekday: one day at 30% extra.
    start_date = date(2026, 12, 1)
    end_date = date(2026, 12, 2)

    price = _calculate_rental_price(500, start_date, end_date)

    assert price == 650


def test_long_rental_discount():
    # Seven rental days, including two weekend days, then 10% off.
    start_date = date(2026, 11, 2)  # Monday
    end_date = start_date + timedelta(days=7)

    price = _calculate_rental_price(500, start_date, end_date)

    # Five weekdays: ₹2,500
    # Two weekend days: ₹1,200
    # Subtotal: ₹3,700
    # After 10% discount: ₹3,330
    assert price == 3330


def test_invalid_rental_duration_is_rejected():
    start_date = date(2026, 11, 2)
    end_date = start_date

    with pytest.raises(HTTPException) as exc_info:
        _calculate_rental_price(500, start_date, end_date)

    assert exc_info.value.status_code == 400
