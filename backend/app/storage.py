from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import DocGateError

T = TypeVar("T", bound=BaseModel)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_json(path: Path, value: BaseModel | dict[str, Any]) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    atomic_write(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())


def read_model(path: Path, model: type[T]) -> T:
    try:
        return model.model_validate_json(path.read_bytes())
    except FileNotFoundError as exc:
        raise DocGateError("NOT_FOUND", "请求的数据不存在。", status=404) from exc
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DocGateError("DATA_CORRUPTED", "会话数据已损坏；原文件已保留，请从备份恢复。", status=500) from exc


@contextmanager
def session_lock(session_dir: Path, *, blocking: bool = False) -> Iterator[None]:
    session_dir.mkdir(parents=True, exist_ok=True)
    lock_path = session_dir / ".lock"
    with lock_path.open("a+b") as handle:
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError as exc:
            raise DocGateError("SESSION_BUSY", "该会话正在写入，请稍后重试。", status=409) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def safe_markdown_path(root: Path, supplied: str, max_bytes: int) -> tuple[Path, str, bytes]:
    if not supplied or Path(supplied).is_absolute():
        raise DocGateError("UNSAFE_PATH", "请选择工作区内的相对 Markdown 路径。")
    candidate = root / supplied
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise DocGateError("UNSAFE_PATH", "文件必须位于当前工作区内。") from exc
    if candidate.is_symlink() or not resolved.is_file() or resolved.suffix.lower() != ".md":
        raise DocGateError("INVALID_FILE", "只支持工作区内的普通 .md 文件。")
    data = resolved.read_bytes()
    if len(data) > max_bytes:
        raise DocGateError("FILE_TOO_LARGE", "Markdown 文件超过 2 MiB 的已验证上限。", status=413)
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocGateError("INVALID_ENCODING", "Markdown 文件必须使用 UTF-8 编码。") from exc
    return resolved, resolved.relative_to(root.resolve()).as_posix(), data
