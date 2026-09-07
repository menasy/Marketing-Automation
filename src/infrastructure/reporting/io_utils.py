"""I/O utilities for resilient file writing under restricted container volume permissions."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_write_text(path: str | Path, content: str, encoding: str = "utf-8") -> Path:
    """Resiliently write text to a file path, handling PermissionError on existing host files.

    If writing to an existing file fails due to host permission mismatch (PermissionError),
    the file is unlinked (deleted) and recreated under the container user's ownership.

    Args:
        path: Target file path.
        content: Text content to write.
        encoding: File encoding (default: utf-8).

    Returns:
        Resolved Path object of written file.
    """
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        target_path.write_text(content, encoding=encoding)
    except PermissionError:
        logger.warning(
            "PermissionError writing to %s. Unlinking file and recreating under process ownership.",
            target_path,
        )
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        target_path.write_text(content, encoding=encoding)

    return target_path
