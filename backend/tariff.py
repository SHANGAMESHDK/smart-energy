def calculate_energy_charge(units: float) -> float:
    if units < 0:
        raise ValueError("Units cannot be negative")

    # Domestic tariff when total consumption <= 500 units
    if units <= 500:
        slabs = [
            (200, 0.00),
            (400, 4.70),
            (500, 6.30),
        ]

    # Domestic tariff when total consumption > 500 units
    else:
        slabs = [
            (100, 0.00),
            (400, 4.70),
            (500, 6.30),
            (600, 8.40),
            (800, 9.45),
            (1000, 10.50),
            (float("inf"), 11.55),
        ]

    charge = 0.0
    previous_limit = 0.0

    for upper_limit, rate in slabs:
        slab_units = max(
            0.0,
            min(units, upper_limit) - previous_limit
        )

        charge += slab_units * rate
        previous_limit = upper_limit

        if units <= upper_limit:
            break

    return round(charge, 2)


if __name__ == "__main__":
    test_units = [100, 200, 400, 450, 499, 500, 501, 510, 600, 800, 1000, 1100]

    print("\nTAMIL NADU EB TARIFF TEST")
    print("-" * 40)

    for units in test_units:
        amount = calculate_energy_charge(units)
        print(f"{units:>4} units  ->  Rs. {amount:,.2f}")
