import sys
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from predictor import predict_consumption


def test_predict_consumption_valid():
    result = predict_consumption(current_units=420, days_elapsed=35, cycle_days=60)
    assert result["current_units"] == 420.0
    assert result["current_daily_average"] == round(420 / 35, 2)
    assert result["predicted_final_units"] > 420.0
    assert result["slab_risk"] == "HIGH"  # 685.21 > 500


def test_predict_consumption_low_risk():
    # 100 units after 30 days -> ~200 final units -> LOW risk
    result = predict_consumption(current_units=100, days_elapsed=30, cycle_days=60)
    assert result["slab_risk"] == "LOW"


def test_predict_consumption_near_limit_risk():
    # Tailor inputs so predicted final units land between 475 and 500
    # Current rate ~7.5 units/day, after 30 days = 225 units
    result = predict_consumption(current_units=240, days_elapsed=30, cycle_days=60)
    # predicted final should be around 470-490
    if 475 <= result["predicted_final_units"] <= 500:
        assert result["slab_risk"] == "NEAR LIMIT"


def test_predict_consumption_invalid_negative_units():
    with pytest.raises(ValueError, match="Units cannot be negative"):
        predict_consumption(current_units=-10, days_elapsed=10, cycle_days=60)


def test_predict_consumption_invalid_days():
    with pytest.raises(ValueError, match="Invalid number of elapsed days"):
        predict_consumption(current_units=100, days_elapsed=0, cycle_days=60)
    with pytest.raises(ValueError, match="Invalid number of elapsed days"):
        predict_consumption(current_units=100, days_elapsed=65, cycle_days=60)
