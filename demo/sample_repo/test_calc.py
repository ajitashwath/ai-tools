from calc import total


def test_total_sums_all_prices():
    assert total([10, 20, 30]) == 60


def test_total_empty():
    assert total([]) == 0


def test_total_single():
    assert total([5]) == 5