import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tariff import calculate_energy_charge


def test_tariff_zero_units():
    assert calculate_energy_charge(0) == 0.0


def test_tariff_negative_units_raises():
    with pytest.raises(ValueError, match="Units cannot be negative"):
        calculate_energy_charge(-5)


def test_tariff_under_200_free_tier():
    # Slabs <= 500 units grant first 200 units at 0.00 rate
    assert calculate_energy_charge(100) == 0.0
    assert calculate_energy_charge(200) == 0.0


def test_tariff_up_to_400_units():
    # 200 units free, next 200 units @ 4.70 = 200 * 4.70 = 940.00
    assert calculate_energy_charge(400) == 940.00


def test_tariff_up_to_500_units():
    # 200 units @ 0 + 200 units @ 4.70 + 100 units @ 6.30 = 940 + 630 = 1570.00
    assert calculate_energy_charge(500) == 1570.00
    # 499 units: 940 + (99 * 6.30) = 940 + 623.70 = 1563.70
    assert calculate_energy_charge(499) == 1563.70


def test_tariff_cliff_jump_at_501_units():
    # At 501 units, free tier drops to 100 units.
    # 100 @ 0 + 300 @ 4.70 + 100 @ 6.30 + 1 @ 8.40 = 0 + 1410 + 630 + 8.40 = 2048.40
    charge_500 = calculate_energy_charge(500)
    charge_501 = calculate_energy_charge(501)
    assert charge_500 == 1570.00
    assert charge_501 == 2048.40
    # Penalty for crossing 500 by just 1 unit is ₹478.40
    assert round(charge_501 - charge_500, 2) == 478.40


def test_tariff_higher_slabs():
    # 600 units: 100@0 + 300@4.70 (1410) + 100@6.30 (630) + 100@8.40 (840) = 2880.00
    assert calculate_energy_charge(600) == 2880.00
    # 800 units: 2880 + 200@9.45 (1890) = 4770.00
    assert calculate_energy_charge(800) == 4770.00
    # 1000 units: 4770 + 200@10.50 (2100) = 6870.00
    assert calculate_energy_charge(1000) == 6870.00
    # 1100 units: 6870 + 100@11.55 (1155) = 8025.00
    assert calculate_energy_charge(1100) == 8025.00
