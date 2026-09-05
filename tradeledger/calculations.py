"""Financial calculations kept independent from the Streamlit UI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation


def money(
    value: object, field: str = "Amount", required: bool = True
) -> Decimal | None:
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError(f"{field} is required.")
        return None
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field} must be a valid number.") from None
    return result


def positive(value: object, field: str) -> Decimal:
    result = money(value, field)
    assert result is not None
    if result <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return result


def dashboard_stats(trades: Iterable[Mapping[str, object]]) -> dict[str, Decimal | int]:
    rows = list(trades)
    closed = [row for row in rows if row.get("status") == "Closed"]
    values = [money(row.get("net_pnl"), "Net P/L") or Decimal(0) for row in closed]
    wins = sum(value > 0 for value in values)
    losses = sum(value < 0 for value in values)
    total = sum(values, Decimal(0))
    count = len(closed)
    return {
        "total_trades": len(rows),
        "open_trades": sum(row.get("status") == "Open" for row in rows),
        "closed_trades": count,
        "wins": wins,
        "losses": losses,
        "win_rate": (Decimal(wins * 100) / Decimal(count)).quantize(Decimal("0.01"))
        if count
        else Decimal(0),
        "total_pnl": total,
        "average": (total / Decimal(count)).quantize(Decimal("0.01"))
        if count
        else Decimal(0),
    }


def cumulative(values: Iterable[object]) -> list[Decimal]:
    running = Decimal(0)
    result = []
    for value in values:
        running += money(value, "Net P/L") or Decimal(0)
        result.append(running)
    return result
