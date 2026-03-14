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
        path_obj = Path(path)
        
        try:
            if path_obj.drive:
                tool_logger.warning({
                    "event_type": "tool_call_blocked",
                    "tool_name": "read_file",
                    "path": path,
                    "reason": "drive_letter_detected"
                })
                raise PermissionError("Drive-based paths not allowed.")
                
            if path_obj.is_absolute():
                path_obj = Path(*path_obj.parts[1:])
                
            file_path = (self.base_dir / path_obj).resolve()

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


    # ---------------------------------------------------------
    # NEW TOOLS BELOW (DO NOT MODIFY EXISTING BEHAVIOR)
    # ---------------------------------------------------------

    def _resolve_safe_path(self, path: str) -> Path:
        path_obj = Path(path)

        if path_obj.drive:
            raise PermissionError("Drive-based paths not allowed.")

        if path_obj.is_absolute():
            path_obj = Path(*path_obj.parts[1:])

        resolved = (self.base_dir / path_obj).resolve()

        if not str(resolved).startswith(str(self.base_dir)):
            raise PermissionError("Path traversal outside workspace denied.")

        return resolved


    def write_file(self, path: str, content: str, overwrite: bool = True) -> str:
        """Create or overwrite a file."""

        try:
            file_path = self._resolve_safe_path(path)

            file_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists() and not overwrite:
                raise FileExistsError("File exists and overwrite disabled.")

            file_path.write_text(content, encoding="utf-8")

            return f"File written successfully: {path}"

        except Exception as e:
            tool_logger.error({
                "event_type": "tool_call_error",
                "tool_name": "write_file",
                "path": path,
                "error": type(e).__name__,
                "message": str(e)
            })

            return f"Error: {str(e)}"


    def list_files(self, path: str = ".", recursive: bool = False) -> list:

        try:
            dir_path = self._resolve_safe_path(path)

            results = []

            iterator = dir_path.rglob("*") if recursive else dir_path.iterdir()

            for item in iterator:
                results.append(str(item.relative_to(self.base_dir)))

            return results

        except Exception as e:
            return [f"Error: {str(e)}"]


    def search_files(self, query: str, path: str = ".", limit: int = 20) -> list:

        try:
            root = self._resolve_safe_path(path)

            results = []

            for file_path in root.rglob("*"):

                if not file_path.is_file():
                    continue

                try:
                    text = file_path.read_text(encoding="utf-8")
                except:
                    continue

                for i, line in enumerate(text.splitlines(), start=1):

                    if query.lower() in line.lower():

                        results.append({
                            "file": str(file_path.relative_to(self.base_dir)),
                            "line": i,
                            "text": line.strip()
                        })

                        if len(results) >= limit:
                            return results

            return results

        except Exception as e:
            return [{"error": str(e)}]


    def patch_file(self, path: str, find: str, replace: str) -> str:

        try:
            file_path = self._resolve_safe_path(path)

            content = file_path.read_text(encoding="utf-8")

            if find not in content:
                return "Patch failed: target text not found."

            new_content = content.replace(find, replace, 1)

            file_path.write_text(new_content, encoding="utf-8")

            return "Patch applied successfully."

        except Exception as e:
            return f"Error: {str(e)}"