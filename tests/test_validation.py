import pytest

from tradeledger.validation import instrument, validate_trade


def test_open_trade_allows_nullable_exit_fields():
    trade = validate_trade(
        {
            "instrument": "XAUUSD",
            "direction": "Long",
            "status": "Open",
            "entry_at": "2026-01-01T10:00",
            "entry_price": "2000",
            "exit_at": None,
            "exit_price": None,
            "stop_loss": "1990",
            "take_profit": "2020",
            "lot_size": "0.10",
            "net_pnl": None,
        }
    )
    assert trade["exit_at"] is None


def test_closed_trade_requires_exit_time():
    with pytest.raises(ValueError, match="Exit date"):
        validate_trade(
            {
                "instrument": "EURUSD",
                "direction": "Short",
                "status": "Closed",
                "entry_at": "2026-01-01T10:00",
                "entry_price": "1.1",
                "lot_size": "1",
                "net_pnl": "2",
            }
        )


def test_closed_trade_requires_exit_price_and_pnl():
    with pytest.raises(ValueError, match="Exit price"):
        validate_trade(
            {
                "instrument": "EURUSD",
                "direction": "Long",
                "status": "Closed",
                "entry_at": "2026-01-01T10:00",
                "exit_at": "2026-01-01T11:00",
                "entry_price": "1.1",
                "lot_size": "1",
                "net_pnl": "2",
            }
        )


def test_exit_before_entry_is_rejected():
    with pytest.raises(ValueError, match="earlier"):
        validate_trade(
            {
                "instrument": "EURUSD",
                "direction": "Long",
                "status": "Closed",
                "entry_at": "2026-01-01T10:00",
                "exit_at": "2026-01-01T09:00",
                "entry_price": "1.1",
                "exit_price": "1.2",
                "lot_size": "1",
                "net_pnl": "2",
            }
        )


def test_instrument_and_positive_values_are_validated():
    assert instrument(" xauusd ") == "XAUUSD"
    with pytest.raises(ValueError, match="greater than zero"):
        validate_trade(
            {
                "instrument": " eurusd ",
                "direction": "Long",
                "status": "Open",
                "entry_at": "2026-01-01T10:00",
                "entry_price": "0",
                "lot_size": "1",
            }
        )
    with pytest.raises(ValueError, match="greater than zero"):
        validate_trade(
            {
                "instrument": " eurusd ",
                "direction": "Long",
                "status": "Open",
                "entry_at": "2026-01-01T10:00",
                "entry_price": "1.1",
                "lot_size": "0",
            }
        )
