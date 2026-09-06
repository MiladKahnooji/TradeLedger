"""TradeLedger Streamlit application."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from tradeledger.calculations import cumulative, dashboard_stats
from tradeledger.database import (
    execute,
    fetch_all,
    fetch_one,
    fetch_trade_screenshots,
    initialize,
)
from tradeledger.screenshots import (
    CATEGORIES,
    MAX_SCREENSHOTS_PER_TRADE,
    delete_screenshot,
    delete_trade_screenshots,
    resolve_owned_path,
    save_screenshot,
    validate_image,
)
from tradeledger.validation import (
    ANALYSIS_DIRECTIONS,
    ANALYSIS_STATUSES,
    ASSESSMENTS,
    DIRECTIONS,
    TRADE_STATUSES,
    instrument,
    required_text,
    validate_trade,
)

DB_PATH = Path(os.environ.get("TRADELEDGER_DB_PATH", "tradeledger.db")).expanduser()
SCREENSHOT_ROOT = Path(
    os.environ.get("TRADELEDGER_SCREENSHOT_ROOT", "screenshots")
).expanduser()
THEMES = ("Dark", "Light")
THEME_PALETTES = {
    "Dark": {
        "app": "#0B1018",
        "surface": "#121925",
        "surface_alt": "#1A2230",
        "sidebar": "#101722",
        "text": "#F4F7FB",
        "muted": "#9AA7B8",
        "border": "#2A3545",
        "accent": "#4F8CFF",
        "positive": "#3CCB7F",
        "negative": "#FF5D6C",
        "warning": "#F5B942",
    },
    "Light": {
        "app": "#F4F7FB",
        "surface": "#FFFFFF",
        "surface_alt": "#EEF2F7",
        "sidebar": "#FFFFFF",
        "text": "#172033",
        "muted": "#667085",
        "border": "#D7DEE8",
        "accent": "#2563EB",
        "positive": "#15803D",
        "negative": "#DC2626",
        "warning": "#B45309",
    },
}
TIMEFRAME_LABELS = {
    "weekly": "Weekly",
    "daily": "Daily",
    "h4": "H4",
    "h1": "H1",
    "m15": "M15",
}


def apply_theme(theme: str) -> None:
    """Apply the stable, session-selected TradeLedger palette."""
    colors = THEME_PALETTES[theme]
    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: {"dark" if theme == "Dark" else "light"}; }}
        [data-testid="stAppViewContainer"] {{ background: {colors["app"]}; color: {colors["text"]}; }}
        [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"] {{ max-width: 1440px; padding-top: 2rem; }}
        [data-testid="stSidebar"] {{ background: {colors["sidebar"]}; border-right: 1px solid {colors["border"]}; }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] label p,
        [data-testid="stSidebar"] button {{ color: {colors["text"]} !important; }}
        [data-testid="stSidebar"] details summary,
        [data-testid="stSidebar"] details summary span,
        [data-testid="stSidebar"] details summary svg {{ color: {colors["text"]} !important; fill: {colors["text"]} !important; stroke: {colors["text"]} !important; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        h1, h2, h3, h4, [data-testid="stMarkdownContainer"] p {{ color: {colors["text"]}; }}
        [data-testid="stMetric"] {{ background: {colors["surface"]}; border: 1px solid {colors["border"]}; border-radius: 10px; padding: 0.8rem 1rem; }}
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{ color: {colors["muted"]} !important; }}
        [data-testid="stMetricValue"], [data-testid="stMetricValue"] div {{ color: {colors["text"]} !important; font-weight: 700; }}
        .tl-metric {{ background: {colors["surface"]}; border: 1px solid {colors["border"]}; border-radius: 10px; padding: 0.8rem 1rem; min-height: 74px; }}
        .tl-metric-label {{ color: {colors["muted"]}; font-size: 0.875rem; }}
        .tl-metric-value {{ font-size: 1.65rem; font-weight: 700; line-height: 1.3; }}
        [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, label, label p {{ color: {colors["text"]} !important; }}
        [data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="textarea"] {{ background: {colors["surface"]}; border-color: {colors["border"]}; color: {colors["text"]}; }}
        [data-baseweb="select"] input, [data-baseweb="select"] span, [data-baseweb="input"] input, textarea {{ color: {colors["text"]} !important; -webkit-text-fill-color: {colors["text"]}; }}
        [data-baseweb="popover"], [role="listbox"], [role="option"] {{ background: {colors["surface"]}; color: {colors["text"]} !important; }}
        [role="option"] {{ border-bottom: 1px solid {colors["border"]}; }}
        [data-testid="stFileUploader"] {{ background: {colors["surface_alt"]}; border: 1px dashed {colors["border"]}; border-radius: 10px; padding: 0.35rem; }}
        [data-testid="stFileUploader"] small, [data-testid="stFileUploader"] p {{ color: {colors["muted"]} !important; }}
        [data-testid="stForm"] {{ background: {colors["surface"]}; border: 1px solid {colors["border"]}; border-radius: 12px; padding: 1rem 1.1rem; }}
        .stButton > button {{ background: {colors["surface"]}; color: {colors["text"]} !important; border: 1px solid {colors["border"]}; border-radius: 8px; }}
        .stButton > button[kind="primary"] {{ background: {colors["accent"]}; border-color: {colors["accent"]}; color: #FFFFFF !important; }}
        .stButton > button:hover {{ border-color: {colors["accent"]}; color: {colors["accent"]} !important; }}
        [data-testid="stAlert"] {{ border: 1px solid {colors["border"]}; }}
        [data-testid="stExpander"] {{ background: {colors["surface"]}; border: 1px solid {colors["border"]}; border-radius: 10px; }}
        [data-testid="stDataFrame"] {{ border: 1px solid {colors["border"]}; border-radius: 8px; }}
        .pnl-positive {{ color: {colors["positive"]}; font-weight: 600; }}
        .pnl-negative {{ color: {colors["negative"]}; font-weight: 600; }}
        .pnl-neutral {{ color: {colors["muted"]}; font-weight: 600; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_template(theme: str) -> str:
    return "plotly_dark" if theme == "Dark" else "plotly_white"


def chart_layout(theme: str) -> dict[str, object]:
    colors = THEME_PALETTES[theme]
    axis = {
        "title_font": {"color": colors["text"]},
        "tickfont": {"color": colors["muted"]},
        "gridcolor": colors["border"],
        "zerolinecolor": colors["muted"],
    }
    return {
        "template": plotly_template(theme),
        "paper_bgcolor": colors["surface"],
        "plot_bgcolor": colors["surface"],
        "font": {"color": colors["text"]},
        "title_font": {"color": colors["text"]},
        "legend": {"font": {"color": colors["text"]}},
        "hoverlabel": {
            "bgcolor": colors["surface_alt"],
            "font": {"color": colors["text"]},
        },
        "xaxis": axis,
        "yaxis": axis.copy(),
    }


def pnl_color(value: object, theme: str) -> str:
    amount = Decimal(str(value)) if value not in (None, "") else Decimal(0)
    palette = THEME_PALETTES[theme]
    if amount > 0:
        return palette["positive"]
    if amount < 0:
        return palette["negative"]
    return palette["text"]


def render_metric(column: object, label: str, value: object, theme: str) -> None:
    if label not in {"Total realized P/L", "Average realized P/L"}:
        column.metric(label, value)
        return
    display_value = fmt_money(value, signed=True)
    color = pnl_color(value, theme)
    column.markdown(
        f'<div class="tl-metric"><div class="tl-metric-label">{label}</div>'
        f'<div class="tl-metric-value" style="color:{color};">{display_value}</div></div>',
        unsafe_allow_html=True,
    )


def screenshot_counter(existing_count: int, newly_selected_count: int) -> str:
    remaining = max(
        0, MAX_SCREENSHOTS_PER_TRADE - existing_count - newly_selected_count
    )
    selected_word = "screenshot" if newly_selected_count == 1 else "screenshots"
    slot_word = "slot" if remaining == 1 else "slots"
    return f"{newly_selected_count} {selected_word} selected · {remaining} of 10 screenshot {slot_word} remaining"


def gallery_metadata(row: object) -> list[tuple[str, str]]:
    metadata = [("Category", row["category"])]
    if row["caption"]:
        metadata.append(("Caption", row["caption"]))
    metadata.extend(
        (
            ("Filename", row["original_filename"]),
            ("Added", fmt_datetime(row["created_at"])),
        )
    )
    return metadata


def fmt_money(value: object, signed: bool = False) -> str:
    amount = Decimal(str(value)) if value not in (None, "") else Decimal(0)
    return (
        f"{'+' if signed and amount > 0 else ''}${amount:,.2f}"
        if amount >= 0
        else f"-${abs(amount):,.2f}"
    )


def fmt_pnl(value: object) -> str:
    if value in (None, ""):
        return "—"
    return fmt_money(value, signed=True)


def fmt_datetime(value: str | None) -> str:
    return (
        f"{datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')} UTC"
        if value
        else "—"
    )


def dt_value(value: str | None) -> datetime:
    return (
        datetime.fromisoformat(value)
        if value
        else datetime.now(timezone.utc).replace(second=0, microsecond=0, tzinfo=None)
    )


def combine_date_time(value_date: date, value_time: time) -> str:
    return datetime.combine(value_date, value_time).isoformat(timespec="minutes")


def screenshot_inputs(
    existing_count: int = 0, key_prefix: str = "trade_screenshot"
) -> list[tuple[object, str, str]]:
    uploads = st.file_uploader(
        "Screenshots (PNG, JPEG, or WebP; up to 10 MB each)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Screenshots are stored locally and never inside SQLite.",
    )
    st.caption(screenshot_counter(existing_count, len(uploads)))
    details: list[tuple[object, str, str]] = []
    for index, upload in enumerate(uploads):
        preview_col, fields_col = st.columns([1, 2])
        with preview_col:
            try:
                validate_image(upload)
                st.image(upload, width=150)
            except ValueError:
                st.warning("Preview unavailable; validation will run when saved.")
        with fields_col:
            st.caption(f"Selected: {upload.name}")
            category = st.selectbox(
                "Category",
                CATEGORIES,
                key=f"{key_prefix}_category_{index}",
            )
            caption = st.text_input(
                "Caption (optional)", key=f"{key_prefix}_caption_{index}"
            )
        details.append((upload, category, caption))
    return details


def save_uploaded_screenshots(
    trade_id: int, uploads: list[tuple[object, str, str]]
) -> None:
    for upload, category, caption in uploads:
        try:
            save_screenshot(
                DB_PATH,
                SCREENSHOT_ROOT,
                trade_id,
                upload,
                category,
                caption,
            )
        except ValueError as exc:
            st.error(f"Screenshot '{getattr(upload, 'name', 'file')}': {exc}")
        except sqlite3.Error:
            st.error(
                f"Screenshot '{getattr(upload, 'name', 'file')}' could not be saved. "
                "The trade itself was kept."
            )


def pnl_markup(value: object) -> str:
    if value in (None, ""):
        return '<span class="pnl-neutral">—</span>'
    amount = Decimal(str(value))
    css_class = (
        "pnl-positive"
        if amount > 0
        else "pnl-negative"
        if amount < 0
        else "pnl-neutral"
    )
    return f'<span class="{css_class}">{fmt_pnl(value)}</span>'


def screenshot_gallery(trade_id: int) -> None:
    rows = fetch_trade_screenshots(DB_PATH, trade_id)
    if not rows:
        st.caption("No screenshots attached.")
        return
    st.markdown(f"**Screenshots** · {len(rows)} attached")
    for start in range(0, len(rows), 2):
        columns = st.columns(min(2, len(rows) - start))
        for column, row in zip(columns, rows[start : start + 2]):
            with column:
                target = None
                try:
                    target = resolve_owned_path(SCREENSHOT_ROOT, row["relative_path"])
                    if not target.is_file():
                        st.warning(
                            f"Missing file: {row['original_filename']}. Remove stale metadata below."
                        )
                    else:
                        st.image(str(target), width=320)
                except ValueError:
                    st.error("A screenshot path is invalid and was not opened.")
                metadata = gallery_metadata(row)
                st.markdown(f"**{metadata[0][1]}**")
                for label, value in metadata[1:]:
                    st.caption(f"{label}: {value}")
                if target is not None and target.is_file():
                    with st.expander("View full size"):
                        st.image(str(target), use_container_width=True)
                delete_key = f"delete_screenshot_{row['id']}"
                if st.button(
                    "Remove metadata"
                    if target is None or not target.is_file()
                    else "Remove",
                    key=delete_key,
                ):
                    st.session_state[f"confirm_{delete_key}"] = True
                if st.session_state.get(f"confirm_{delete_key}"):
                    st.warning("Remove this screenshot permanently?")
                    if st.button("Confirm removal", key=f"confirm_{delete_key}_button"):
                        try:
                            delete_screenshot(DB_PATH, SCREENSHOT_ROOT, row["id"])
                            st.session_state.pop(f"confirm_{delete_key}", None)
                            st.success("Screenshot removed.")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                        except sqlite3.Error:
                            st.error(
                                "Could not remove the screenshot. Please try again."
                            )


def add_account() -> None:
    st.subheader("New trading account")
    with st.form("account_form"):
        st.markdown("#### Account details")
        name = st.text_input("Account name")
        broker = st.text_input("Broker name")
        balance = st.number_input(
            "Initial balance (USD)", min_value=0.0, step=100.0, format="%.2f"
        )
        if st.form_submit_button("Create account", type="primary"):
            try:
                account_name = required_text(name, "Account name")
                broker_name = required_text(broker, "Broker name")
                account_id = execute(
                    DB_PATH,
                    "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
                    (account_name, broker_name, f"{balance:.2f}"),
                )
                st.success(f"Account #{account_id} created.")
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.Error:
                st.error("Could not save the account. Please try again.")


def account_options() -> list[object]:
    return fetch_all(DB_PATH, "SELECT id, name, broker FROM accounts ORDER BY name")


def analysis_label(row: object) -> str:
    return f"#{row['id']} · {row['instrument']} · {row['direction']} · {fmt_datetime(row['analysis_at'])}"


def analysis_form() -> None:
    st.subheader("New pre-trade analysis")
    with st.form("analysis_form"):
        st.markdown("#### Market context")
        instrument_value = st.text_input("Instrument", placeholder="EURUSD or XAUUSD")
        direction = st.selectbox("Intended direction", ANALYSIS_DIRECTIONS)
        analysis_date = st.date_input(
            "Analysis date", value=datetime.now(timezone.utc).date()
        )
        analysis_time = st.time_input(
            "Analysis time",
            value=datetime.now(timezone.utc).time().replace(second=0, microsecond=0),
        )
        status = st.selectbox("Status", ANALYSIS_STATUSES)
        assessments = {
            key: st.selectbox(
                f"{label} assessment", ASSESSMENTS, index=3, key=f"analysis_{key}"
            )
            for key, label in TIMEFRAME_LABELS.items()
        }
        notes = st.text_area("Notes")
        st.markdown("**Pre-trade checklist**")
        for index, item in enumerate(
            (
                "Higher-timeframe direction reviewed",
                "Risk and invalidation considered",
                "Entry area identified",
            )
        ):
            st.checkbox(item, key=f"check_{index}")
        if st.form_submit_button("Save analysis", type="primary"):
            try:
                values = [
                    instrument(instrument_value),
                    direction,
                    combine_date_time(analysis_date, analysis_time),
                    notes.strip(),
                    *assessments.values(),
                    status,
                ]
                analysis_id = execute(
                    DB_PATH,
                    "INSERT INTO analyses(instrument, direction, analysis_at, notes, weekly, daily, h4, h1, m15, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(values),
                )
                st.success(f"Analysis #{analysis_id} saved.")
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.Error:
                st.error("Could not save the analysis. Please try again.")
    recent = fetch_all(
        DB_PATH,
        "SELECT id, instrument, direction, status, analysis_at FROM analyses ORDER BY id DESC LIMIT 10",
    )
    if recent:
        st.markdown("**Recent analyses**")
        st.dataframe(
            [
                {
                    "ID": row["id"],
                    "Instrument": row["instrument"],
                    "Direction": row["direction"],
                    "Status": row["status"],
                    "Analysis time": fmt_datetime(row["analysis_at"]),
                }
                for row in recent
            ],
            use_container_width=True,
            hide_index=True,
        )


def relation_warning(
    direction: str, stop_loss: object, entry_price: object, take_profit: object
) -> str | None:
    if stop_loss in (None, "") or take_profit in (None, ""):
        return None
    entry, stop, target = (
        Decimal(str(entry_price)),
        Decimal(str(stop_loss)),
        Decimal(str(take_profit)),
    )
    if direction == "Long" and not stop < entry < target:
        return "For a Long trade, the usual relationship is SL < Entry < TP."
    if direction == "Short" and not target < entry < stop:
        return "For a Short trade, the usual relationship is TP < Entry < SL."
    return None


def trade_form(existing: object | None = None) -> None:
    editing = existing is not None
    st.subheader("Edit trade" if editing else "New manual trade")
    accounts = account_options()
    if not accounts:
        st.info("Create a trading account first.")
        return
    current = dict(existing) if existing else {}
    analyses = fetch_all(
        DB_PATH,
        "SELECT id, instrument, direction, analysis_at FROM analyses ORDER BY analysis_at DESC",
    )
    account_ids = [row["id"] for row in accounts]
    analysis_ids = [None, *[row["id"] for row in analyses]]
    selected_analysis = current.get("analysis_id")
    analysis_index = (
        analysis_ids.index(selected_analysis)
        if selected_analysis in analysis_ids
        else 0
    )
    default_direction = current.get("direction", "Long")
    with st.form("trade_form"):
        st.markdown("#### Trade details")
        account_id = st.selectbox(
            "Account",
            account_ids,
            index=account_ids.index(current.get("account_id", account_ids[0])),
            format_func=lambda item: next(
                row["name"] for row in accounts if row["id"] == item
            ),
        )
        analysis_id = st.selectbox(
            "Linked pre-trade analysis (optional)",
            analysis_ids,
            index=analysis_index,
            format_func=lambda item: (
                "None"
                if item is None
                else analysis_label(next(row for row in analyses if row["id"] == item))
            ),
        )
        linked = next((row for row in analyses if row["id"] == analysis_id), None)
        suggested_instrument = (
            linked["instrument"] if linked else current.get("instrument", "")
        )
        suggested_direction = (
            linked["direction"]
            if linked and linked["direction"] in DIRECTIONS
            else default_direction
        )
        instrument_value = st.text_input("Instrument", value=suggested_instrument)
        direction = st.selectbox(
            "Direction", DIRECTIONS, index=DIRECTIONS.index(suggested_direction)
        )
        status = st.selectbox(
            "Status",
            TRADE_STATUSES,
            index=TRADE_STATUSES.index(current.get("status", "Open")),
        )
        entry_default = dt_value(current.get("entry_at"))
        st.markdown("#### Entry and pricing")
        entry_col1, entry_col2 = st.columns(2)
        with entry_col1:
            entry_day = st.date_input("Entry date", value=entry_default.date())
        with entry_col2:
            entry_clock = st.time_input("Entry time", value=entry_default.time())
        prices = st.columns(2)
        with prices[0]:
            entry_price = st.text_input(
                "Entry price", value=str(current.get("entry_price", ""))
            )
        with prices[1]:
            lot_size = st.text_input("Lot size", value=str(current.get("lot_size", "")))
        levels = st.columns(2)
        with levels[0]:
            stop_loss = st.text_input(
                "Stop loss (optional)", value=str(current.get("stop_loss") or "")
            )
        with levels[1]:
            take_profit = st.text_input(
                "Take profit (optional)", value=str(current.get("take_profit") or "")
            )
        if status == "Closed":
            st.markdown("#### Exit and realized result")
            exit_default = dt_value(current.get("exit_at"))
            exit_col1, exit_col2 = st.columns(2)
            with exit_col1:
                exit_day = st.date_input("Exit date", value=exit_default.date())
            with exit_col2:
                exit_clock = st.time_input("Exit time", value=exit_default.time())
            exit_price = st.text_input(
                "Exit price", value=str(current.get("exit_price") or "")
            )
            net_pnl = st.text_input(
                "Net profit/loss (USD)",
                value=""
                if current.get("net_pnl") is None
                else str(current.get("net_pnl")),
            )
        else:
            exit_day = exit_clock = exit_price = net_pnl = None
            st.caption(
                "Exit details and realized P/L are available after marking the trade Closed."
            )
        st.markdown("#### Screenshots")
        existing_screenshot_count = (
            len(fetch_trade_screenshots(DB_PATH, current["id"])) if editing else 0
        )
        screenshot_uploads = screenshot_inputs(
            existing_screenshot_count,
            "edit_trade_screenshot" if editing else "new_trade_screenshot",
        )
        notes = st.text_area("Notes", value=current.get("notes", ""))
        submitted = st.form_submit_button(
            "Update trade" if editing else "Save trade", type="primary"
        )
        if submitted:
            try:
                remaining_screenshot_slots = max(
                    0, MAX_SCREENSHOTS_PER_TRADE - existing_screenshot_count
                )
                if len(screenshot_uploads) > remaining_screenshot_slots:
                    raise ValueError(
                        f"Select no more than {remaining_screenshot_slots} additional screenshots."
                    )
                data = {
                    "instrument": instrument_value,
                    "direction": direction,
                    "status": status,
                    "entry_at": combine_date_time(entry_day, entry_clock),
                    "exit_at": combine_date_time(exit_day, exit_clock)
                    if status == "Closed"
                    else None,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "lot_size": lot_size,
                    "net_pnl": net_pnl,
                }
                validated = validate_trade(data)
                warning = relation_warning(
                    direction,
                    validated["stop_loss"],
                    validated["entry_price"],
                    validated["take_profit"],
                )
                if warning:
                    st.warning(warning)
                values = (
                    account_id,
                    analysis_id,
                    validated["instrument"],
                    direction,
                    validated["entry_at"],
                    validated["exit_at"],
                    str(validated["entry_price"]),
                    str(validated["exit_price"])
                    if validated["exit_price"] is not None
                    else None,
                    str(validated["stop_loss"])
                    if validated["stop_loss"] is not None
                    else None,
                    str(validated["take_profit"])
                    if validated["take_profit"] is not None
                    else None,
                    str(validated["lot_size"]),
                    str(validated["net_pnl"])
                    if validated["net_pnl"] is not None
                    else None,
                    notes.strip(),
                    status,
                )
                if editing:
                    execute(
                        DB_PATH,
                        "UPDATE trades SET account_id=?, analysis_id=?, instrument=?, direction=?, entry_at=?, exit_at=?, entry_price=?, exit_price=?, stop_loss=?, take_profit=?, lot_size=?, net_pnl=?, notes=?, status=? WHERE id=?",
                        (*values, current["id"]),
                    )
                    save_uploaded_screenshots(current["id"], screenshot_uploads)
                    st.success(f"Trade #{current['id']} updated.")
                else:
                    trade_id = execute(
                        DB_PATH,
                        "INSERT INTO trades(account_id, analysis_id, instrument, direction, entry_at, exit_at, entry_price, exit_price, stop_loss, take_profit, lot_size, net_pnl, notes, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values,
                    )
                    save_uploaded_screenshots(trade_id, screenshot_uploads)
                    st.success(f"Trade #{trade_id} saved.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except sqlite3.Error:
                st.error("Could not save the trade. Please try again.")


def dashboard() -> None:
    accounts = account_options()
    account_filter = st.selectbox(
        "Account",
        [None, *[row["id"] for row in accounts]],
        format_func=lambda item: (
            "All accounts"
            if item is None
            else next(row["name"] for row in accounts if row["id"] == item)
        ),
    )
    query = "SELECT * FROM trades WHERE 1=1"
    params: list[object] = []
    if account_filter is not None:
        query += " AND account_id = ?"
        params.append(account_filter)
    trades = fetch_all(DB_PATH, query, tuple(params))
    stats = dashboard_stats([dict(row) for row in trades])
    labels = (
        ("Total trades", stats["total_trades"]),
        ("Open trades", stats["open_trades"]),
        ("Closed trades", stats["closed_trades"]),
        ("Winning trades", stats["wins"]),
        ("Losing trades", stats["losses"]),
        (
            "Win rate",
            f"{Decimal(stats['win_rate']).quantize(Decimal('0.1'))}%",
        ),
        ("Total realized P/L", stats["total_pnl"]),
        ("Average realized P/L", stats["average"]),
    )
    theme = st.session_state.get("theme", "Dark")
    for row in (labels[:3], labels[3:6], labels[6:]):
        cols = st.columns(3)
        for col, (label, value) in zip(cols, row):
            render_metric(col, label, value, theme)
    closed = sorted(
        [row for row in trades if row["status"] == "Closed"],
        key=lambda row: (row["exit_at"] or row["entry_at"], row["id"]),
    )
    if closed:
        values = cumulative(row["net_pnl"] for row in closed)
        figure = go.Figure(
            go.Scatter(
                x=[
                    "",
                    *[
                        fmt_datetime(row["exit_at"] or row["entry_at"])
                        for row in closed
                    ],
                ],
                y=[0.0, *[float(value) for value in values]],
                mode="lines+markers",
            )
        )
        figure.update_layout(
            title="Cumulative Realized P/L",
            xaxis_title="Trade date",
            yaxis_title="USD",
            autosize=True,
            **chart_layout(theme),
        )
        figure.add_hline(y=0, line_color=THEME_PALETTES[theme]["muted"], line_width=1)
        st.plotly_chart(figure, use_container_width=True)
    else:
        st.info("No closed trades yet. Add a closed trade to see realized performance.")


def trade_detail(row: object) -> None:
    analysis = (
        fetch_one(
            DB_PATH,
            "SELECT id, instrument, direction, analysis_at FROM analyses WHERE id = ?",
            (row["analysis_id"],),
        )
        if row["analysis_id"]
        else None
    )
    st.markdown(f"**Trade #{row['id']}**")
    details = (
        ("Account", row["account_name"]),
        ("Instrument", row["instrument"]),
        ("Direction", row["direction"]),
        ("Status", row["status"]),
        ("Entry", fmt_datetime(row["entry_at"])),
        ("Exit", fmt_datetime(row["exit_at"])),
        ("Entry price", row["entry_price"]),
        ("Exit price", row["exit_price"] or "—"),
        ("Stop loss", row["stop_loss"] or "—"),
        ("Take profit", row["take_profit"] or "—"),
        ("Lot size", row["lot_size"]),
        ("Linked analysis", analysis_label(analysis) if analysis else "None"),
        ("Notes", row["notes"] or "—"),
    )
    st.dataframe(
        [{"Field": label, "Value": value} for label, value in details],
        hide_index=True,
        use_container_width=True,
    )
    st.markdown(f"Net P/L: {pnl_markup(row['net_pnl'])}", unsafe_allow_html=True)
    screenshot_gallery(row["id"])


def history() -> None:
    st.subheader("Journal history")
    accounts = account_options()
    account_filter = st.selectbox(
        "Account",
        [None, *[row["id"] for row in accounts]],
        format_func=lambda item: (
            "All accounts"
            if item is None
            else next(row["name"] for row in accounts if row["id"] == item)
        ),
    )
    instrument_filter = st.text_input("Instrument contains")
    direction_filter = st.selectbox("Direction", ["All", *DIRECTIONS])
    status_filter = st.selectbox("Status", ["All", *TRADE_STATUSES])
    query = "SELECT trades.*, accounts.name AS account_name FROM trades JOIN accounts ON accounts.id = trades.account_id WHERE 1=1"
    parameters: list[object] = []
    if account_filter is not None:
        query += " AND trades.account_id = ?"
        parameters.append(account_filter)
    if instrument_filter.strip():
        query += " AND trades.instrument LIKE ?"
        parameters.append(f"%{instrument_filter.strip().upper()}%")
    if direction_filter != "All":
        query += " AND trades.direction = ?"
        parameters.append(direction_filter)
    if status_filter != "All":
        query += " AND trades.status = ?"
        parameters.append(status_filter)
    rows = fetch_all(
        DB_PATH,
        query + " ORDER BY COALESCE(exit_at, entry_at) DESC, id DESC",
        tuple(parameters),
    )
    if not rows:
        st.info("No trades match the selected filters.")
        return
    st.dataframe(
        [
            {
                "ID": row["id"],
                "Account": row["account_name"],
                "Instrument": row["instrument"],
                "Direction": row["direction"],
                "Status": row["status"],
                "Entry": fmt_datetime(row["entry_at"]),
                "Exit": fmt_datetime(row["exit_at"]),
                "Net P/L": fmt_pnl(row["net_pnl"]),
            }
            for row in rows
        ],
        use_container_width=True,
        hide_index=True,
    )
    selected = st.selectbox(
        "View or edit trade",
        [row["id"] for row in rows],
        format_func=lambda item: next(
            f"#{row['id']} · {row['instrument']} · {row['direction']} · {fmt_datetime(row['entry_at'])}"
            for row in rows
            if row["id"] == item
        ),
    )
    row = fetch_one(
        DB_PATH,
        "SELECT trades.*, accounts.name AS account_name FROM trades JOIN accounts ON accounts.id = trades.account_id WHERE trades.id = ?",
        (selected,),
    )
    if row:
        with st.expander(f"Trade #{selected} details", expanded=True):
            trade_detail(row)
        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("Edit this trade", key=f"edit_{selected}"):
                st.session_state["edit_trade"] = selected
                st.rerun()
        with delete_col:
            if st.button("Delete this trade", key=f"delete_{selected}"):
                st.session_state["confirm_delete"] = selected
        if st.session_state.get("confirm_delete") == selected:
            st.warning(
                "This permanently deletes only the selected trade. Its account and analysis will remain."
            )
            if st.button("Confirm permanent deletion", key=f"confirm_{selected}"):
                try:
                    delete_trade_screenshots(DB_PATH, SCREENSHOT_ROOT, selected)
                    st.session_state.pop("confirm_delete", None)
                    st.success(f"Trade #{selected} deleted.")
                    st.rerun()
                except sqlite3.Error:
                    st.error("Could not delete the trade. Please try again.")
        if st.session_state.get("edit_trade") == selected:
            trade_form(row)


def demo_exists() -> bool:
    return (
        fetch_one(
            DB_PATH,
            "SELECT id FROM accounts WHERE name = ? AND broker = ? LIMIT 1",
            ("Demo account", "Demo broker"),
        )
        is not None
    )


def add_demo_data() -> bool:
    if demo_exists():
        return False
    account_id = execute(
        DB_PATH,
        "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
        ("Demo account", "Demo broker", "10000.00"),
    )
    execute(
        DB_PATH,
        "INSERT INTO trades(account_id, instrument, direction, entry_at, exit_at, entry_price, exit_price, lot_size, net_pnl, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            account_id,
            "XAUUSD",
            "Long",
            "2026-01-05T10:00",
            "2026-01-05T12:00",
            "2000",
            "2010",
            "0.10",
            "100.00",
            "Closed",
        ),
    )
    execute(
        DB_PATH,
        "INSERT INTO trades(account_id, instrument, direction, entry_at, exit_at, entry_price, exit_price, lot_size, net_pnl, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            account_id,
            "EURUSD",
            "Short",
            "2026-01-06T10:00",
            "2026-01-06T12:00",
            "1.1",
            "1.102",
            "1.00",
            "-20.00",
            "Closed",
        ),
    )
    return True


def main() -> None:
    st.set_page_config(
        page_title="TradeLedger",
        page_icon="📒",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    initialize(DB_PATH)
    if "theme" not in st.session_state:
        st.session_state["theme"] = "Dark"
    selected_theme = st.sidebar.selectbox(
        "Theme", THEMES, index=THEMES.index(st.session_state["theme"])
    )
    st.session_state["theme"] = selected_theme
    apply_theme(selected_theme)
    st.title("TradeLedger")
    st.caption("A privacy-focused local trading journal · USD · Forex and Gold")
    page = st.sidebar.radio(
        "Navigate",
        (
            "Dashboard",
            "Trading accounts",
            "Pre-trade analysis",
            "Manual trade entry",
            "Journal history",
        ),
    )
    with st.sidebar.expander("Demo tools"):
        st.caption("Optional sample account and trades")
        if demo_exists():
            st.info("Demo data is already present.")
        elif st.button("Insert demo data"):
            st.session_state["confirm_demo"] = True
        if st.session_state.get("confirm_demo") and not demo_exists():
            st.warning("Insert sample records into this local database?")
            if st.button("Confirm demo insertion"):
                add_demo_data()
                st.session_state.pop("confirm_demo", None)
                st.success("Demo data inserted.")
                st.rerun()
    if page == "Dashboard":
        dashboard()
    elif page == "Trading accounts":
        add_account()
        st.subheader("Accounts")
        st.dataframe(
            [
                {
                    "ID": row["id"],
                    "Account": row["name"],
                    "Broker": row["broker"],
                    "Initial Balance": fmt_money(row["initial_balance"]),
                    "Currency": row["currency"],
                }
                for row in fetch_all(
                    DB_PATH,
                    "SELECT id, name, broker, initial_balance, currency FROM accounts ORDER BY name",
                )
            ],
            use_container_width=True,
            hide_index=True,
        )
    elif page == "Pre-trade analysis":
        analysis_form()
    elif page == "Manual trade entry":
        trade_form()
    elif st.session_state.get("edit_trade"):
        row = fetch_one(
            DB_PATH,
            "SELECT * FROM trades WHERE id = ?",
            (st.session_state["edit_trade"],),
        )
        if row:
            trade_form(row)
        if st.button("Back to journal"):
            st.session_state.pop("edit_trade")
            st.rerun()
    else:
        history()


if __name__ == "__main__":
    main()
