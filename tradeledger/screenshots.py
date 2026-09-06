"""Safe local screenshot storage for trade records."""

from __future__ import annotations

import sqlite3
import uuid
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from PIL import Image, UnidentifiedImageError

from .database import connect, fetch_all, fetch_one

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_SCREENSHOTS_PER_TRADE = 10
CATEGORIES = ("Before Entry", "After Exit", "Other")
_FORMATS = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}


def _upload_value(upload: Any) -> tuple[str, bytes]:
    name = str(getattr(upload, "name", "upload"))
    if hasattr(upload, "getvalue"):
        data = bytes(upload.getvalue())
    elif isinstance(upload, (bytes, bytearray)):
        data = bytes(upload)
    else:
        raise ValueError("The selected screenshot could not be read.")
    return name, data


def validate_image(upload: Any) -> tuple[str, str, bytes]:
    """Return original name, verified content type, and bytes."""
    name, data = _upload_value(upload)
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("Each screenshot must be 10 MB or smaller.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            image_format = image.format.upper() if image.format else ""
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("The screenshot is not a valid supported image.") from None
    if image_format not in _FORMATS:
        raise ValueError("Only PNG, JPEG, and WebP screenshots are supported.")
    content_type, _ = _FORMATS[image_format]
    return Path(name).name or "screenshot", content_type, data


def resolve_owned_path(root: str | Path, relative_path: str) -> Path:
    """Resolve a managed relative path, rejecting traversal and absolute paths."""
    normalized = relative_path.replace("\\", "/")
    if (
        not relative_path
        or PurePosixPath(normalized).is_absolute()
        or PureWindowsPath(relative_path).is_absolute()
        or ".." in PurePosixPath(normalized).parts
    ):
        raise ValueError("Screenshot path must be relative.")
    root_path = Path(root).expanduser().resolve()
    target = (root_path / Path(relative_path)).resolve()
    try:
        target.relative_to(root_path)
    except ValueError:
        raise ValueError(
            "Screenshot path is outside the managed screenshot folder."
        ) from None
    return target


def _next_relative_path(
    root: Path, trade_id: int, content_type: str
) -> tuple[str, Path]:
    suffix = next(suffix for mime, suffix in _FORMATS.values() if mime == content_type)
    trade_folder = root / str(trade_id)
    trade_folder.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        filename = f"{uuid.uuid4().hex}{suffix}"
        relative = f"{trade_id}/{filename}"
        target = resolve_owned_path(root, relative)
        if not target.exists():
            return relative, target
    raise OSError("Could not generate a unique screenshot filename.")


def save_screenshot(
    db_path: str | Path,
    root: str | Path,
    trade_id: int,
    upload: Any,
    category: str,
    caption: str = "",
) -> int:
    if category not in CATEGORIES:
        raise ValueError("Choose a valid screenshot category.")
    trade = fetch_one(db_path, "SELECT id FROM trades WHERE id = ?", (trade_id,))
    if trade is None:
        raise ValueError("The trade no longer exists.")
    current_count = fetch_one(
        db_path,
        "SELECT COUNT(*) AS count FROM trade_screenshots WHERE trade_id = ?",
        (trade_id,),
    )["count"]
    if current_count >= MAX_SCREENSHOTS_PER_TRADE:
        raise ValueError("A trade can have at most 10 screenshots.")
    original_name, content_type, data = validate_image(upload)
    root_path = Path(root).expanduser().resolve()
    try:
        relative_path, target = _next_relative_path(root_path, trade_id, content_type)
        target.write_bytes(data)
    except OSError:
        raise ValueError("The screenshot could not be stored locally.") from None
    try:
        with connect(db_path) as connection:
            cursor = connection.execute(
                "INSERT INTO trade_screenshots(trade_id, relative_path, original_filename, category, caption, content_type, file_size) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    trade_id,
                    relative_path,
                    original_name,
                    category,
                    str(caption or "").strip(),
                    content_type,
                    len(data),
                ),
            )
            return int(cursor.lastrowid)
    except sqlite3.Error:
        target.unlink(missing_ok=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass
        raise


def delete_screenshot(
    db_path: str | Path, root: str | Path, screenshot_id: int
) -> bool:
    row = fetch_one(
        db_path,
        "SELECT relative_path FROM trade_screenshots WHERE id = ?",
        (screenshot_id,),
    )
    if row is None:
        return False
    target = resolve_owned_path(root, row["relative_path"])
    target.unlink(missing_ok=True)
    try:
        target.parent.rmdir()
    except OSError:
        pass
    with connect(db_path) as connection:
        connection.execute(
            "DELETE FROM trade_screenshots WHERE id = ?", (screenshot_id,)
        )
    return True


def delete_trade_screenshots(
    db_path: str | Path, root: str | Path, trade_id: int
) -> None:
    rows = fetch_all(
        db_path,
        "SELECT relative_path FROM trade_screenshots WHERE trade_id = ?",
        (trade_id,),
    )
    with connect(db_path) as connection:
        connection.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    for row in rows:
        try:
            resolve_owned_path(root, row["relative_path"]).unlink(missing_ok=True)
        except ValueError:
            # The metadata is already gone; never touch an unsafe path.
            continue
