from decimal import Decimal

import pytest

from tradeledger.calculations import cumulative, dashboard_stats, money


def test_dashboard_stats_and_cumulative():
    stats = dashboard_stats(
        [
            {"status": "Open", "net_pnl": None},
            {"status": "Closed", "net_pnl": "10.00"},
            {"status": "Closed", "net_pnl": "-4.50"},
            {"status": "Closed", "net_pnl": "0"},
        ]
    )
    assert stats["total_trades"] == 4
    assert stats["open_trades"] == 1
    assert stats["closed_trades"] == 3
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate"] == Decimal("33.33")
    assert stats["total_pnl"] == Decimal("5.50")
    assert cumulative(["10", "-4.50"]) == [Decimal("10.00"), Decimal("5.50")]


def test_dashboard_stats_empty_dataset():
    stats = dashboard_stats([])
    assert stats["total_trades"] == 0
    assert stats["win_rate"] == Decimal(0)
    assert stats["total_pnl"] == Decimal(0)


def test_money_rejects_invalid_values():
    with pytest.raises(ValueError, match="valid number"):
        money("abc")
