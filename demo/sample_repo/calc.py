"""Sample calc module for the AI DevTools sandbox demo.

This file ships with an intentional bug: ``total`` skips the first price.
The sandbox agent repairs it via ``repair.py`` and re-runs the tests.
"""


def total(prices: list[float]) -> float:
    return sum(prices[1:])