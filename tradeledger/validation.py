"""Shared input validation for forms."""

from __future__ import annotations

from datetime import datetime

from .calculations import money, positive

TIMEFRAMES = ("weekly", "daily", "h4", "h1", "m15")
ASSESSMENTS = ("Bullish", "Bearish", "Neutral", "Not Assessed")
ANALYSIS_DIRECTIONS = ("Undecided", "Long", "Short")
DIRECTIONS = ("Long", "Short")
ANALYSIS_STATUSES = ("Draft", "Ready", "Executed", "Skipped")
TRADE_STATUSES = ("Open", "Closed")


def required_text(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required.")
    return text


def instrument(value: object) -> str:
    return required_text(str(value or ""), "Instrument").upper()


def parse_datetime(
    value: str | datetime | None, field: str, required: bool = True
) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"{field} is required.")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            raise ValueError(f"{field} must be a valid date and time.") from None
    return parsed.isoformat(timespec="minutes")


def validate_trade(data: dict[str, object]) -> dict[str, object]:
    result = dict(data)
    result["instrument"] = instrument(data.get("instrument"))
    if data.get("direction") not in DIRECTIONS:
        raise ValueError("Direction must be Long or Short.")
    if data.get("status") not in TRADE_STATUSES:
        raise ValueError("Status must be Open or Closed.")
    result["entry_at"] = parse_datetime(data.get("entry_at"), "Entry date and time")
    if result["status"] == "Open":
        result["exit_at"] = None
    else:
        result["exit_at"] = parse_datetime(data.get("exit_at"), "Exit date and time")
    result["entry_price"] = positive(data.get("entry_price"), "Entry price")
    result["exit_price"] = (
        positive(data.get("exit_price"), "Exit price")
        if result["status"] == "Closed"
        else None
    )
    result["stop_loss"] = (
        positive(data.get("stop_loss"), "Stop loss")
        if data.get("stop_loss") not in (None, "")
        else None
    )
    result["take_profit"] = (
        positive(data.get("take_profit"), "Take profit")
        if data.get("take_profit") not in (None, "")
        else None
    )
    result["lot_size"] = positive(data.get("lot_size"), "Lot size")
    result["net_pnl"] = (
        money(data.get("net_pnl"), "Net profit/loss")
        if result["status"] == "Closed"
        else None
    )
    if result["status"] == "Closed" and result["exit_at"] < result["entry_at"]:
        raise ValueError(
            "Exit date and time cannot be earlier than entry date and time."
        )
    return result
