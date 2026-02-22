import os
from pathlib import Path
from app.logger import tool_logger

class FilesTool:
    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            self.base_dir = Path.cwd().resolve()
        else:
            self.base_dir = Path(base_dir).resolve()

    def read_file(self, path: str) -> str:
        """Read a file from disk, returning its contents as a string."""
        tool_logger.info({
            "event_type": "tool_call_start",
            "tool_name": "read_file",
            "path": path,
        })
        try:
            # Strip leading slashes so Path concatenation doesn't reset to drive root
            clean_path = path.lstrip("/\\")
            file_path = (self.base_dir / clean_path).resolve()

            if not str(file_path).startswith(str(self.base_dir)):
                tool_logger.warning({
                    "event_type": "tool_call_blocked",
                    "tool_name": "read_file",
                    "path": path,
                    "reason": "path_traversal",
                    "resolved_path": str(file_path)
                })
                raise PermissionError(f"Access denied to {path}")

            if not file_path.exists():
                tool_logger.warning({
                    "event_type": "tool_call_failed",
                    "tool_name": "read_file",
                    "path": path,
                    "reason": "file_not_found"
                })
                raise FileNotFoundError(f"File not found: {path}")

            if not file_path.is_file():
                tool_logger.warning({
                    "event_type": "tool_call_failed",
                    "tool_name": "read_file",
                    "path": path,
                    "reason": "not_a_file"
                })
                raise ValueError(f"Path is not a regular file: {path}")

            if file_path.stat().st_size > 1_000_000:
                tool_logger.warning({
                    "event_type": "tool_call_failed",
                    "tool_name": "read_file",
                    "path": path,
                    "reason": "file_too_large"
                })
                raise ValueError(f"File too large: {path}")

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback for common Windows encodings (e.g. utf-16le BOM)
                tool_logger.info({
                    "event_type": "tool_call_retry_encoding",
                    "tool_name": "read_file",
                    "path": path,
                    "encoding_tried": "utf-16"
                })
                content = file_path.read_text(encoding="utf-16")
                
            tool_logger.info({
                "event_type": "tool_call_success",
                "tool_name": "read_file",
                "path": path,
                "read_bytes": len(content)
            })
            return content

        except UnicodeDecodeError as e:
            tool_logger.error({
                "event_type": "tool_call_error",
                "tool_name": "read_file",
                "path": path,
                "error": "UnicodeDecodeError",
                "message": str(e)
            })
            return f"Error: Cannot read file {path} as text (encoding issue)."
        except Exception as e:
            tool_logger.error({
                "event_type": "tool_call_error",
                "tool_name": "read_file",
                "path": path,
                "error": type(e).__name__,
                "message": str(e)
            })
            return f"Error: {str(e)}"
