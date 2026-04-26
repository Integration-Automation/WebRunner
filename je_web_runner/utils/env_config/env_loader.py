"""
依環境別載入 .env 檔，並在 action JSON 中展開 ``${ENV.KEY}`` 占位符。
Per-environment .env loader plus ``${ENV.KEY}`` placeholder expansion in
action JSON. Lets the same action script run against dev / staging / prod
without hard-coded URLs or credentials.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class EnvConfigError(WebRunnerException):
    """Raised when an env file cannot be loaded or a placeholder is missing."""


_PLACEHOLDER_RE = re.compile(r"\$\{ENV\.([A-Za-z_]\w*)\}")


def load_env(env_name: Optional[str] = None, env_dir: str = ".", override: bool = False) -> str:
    """
    載入指定環境的 ``.env`` 檔
    Load the ``.env`` file for the given environment.

    :param env_name: 環境名稱；None 時讀 ``.env``，否則讀 ``.env.<env_name>``
                      ``None`` reads ``.env``; otherwise ``.env.<env_name>``.
    :param env_dir: ``.env`` 檔所在資料夾 / directory holding the env files
    :param override: 是否覆蓋已存在的環境變數 / whether to overwrite existing
                      values in ``os.environ``
    :return: 實際載入的檔案路徑 / the file path that was loaded
    """
    file_name = ".env" if not env_name else f".env.{env_name}"
    target = Path(env_dir) / file_name
    if not target.exists():
        raise EnvConfigError(f"env file not found: {target}")
    web_runner_logger.info(f"load_env: {target}")
    load_dotenv(dotenv_path=target, override=override)
    return str(target)


def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Return ``os.environ[key]`` with an optional default."""
    return os.environ.get(key, default)


def _expand_string(text: str) -> str:
    def _resolve(match: re.Match) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise EnvConfigError(f"unresolved placeholder: ${{ENV.{name}}}")
        return os.environ[name]

    return _PLACEHOLDER_RE.sub(_resolve, text)


def expand_in_action(data: Any) -> Any:
    """
    遞迴展開 ``${ENV.KEY}`` 占位符
    Recursively expand ``${ENV.KEY}`` placeholders inside an action structure.

    支援 ``str`` / ``dict`` / ``list`` / ``tuple``。其他型別原樣回傳。
    Strings, dicts, lists and tuples are walked; other values pass through.

    :raises EnvConfigError: 找到無法解析的占位符時 / on a missing placeholder
    """
    if isinstance(data, str):
        return _expand_string(data)
    if isinstance(data, dict):
        return {key: expand_in_action(value) for key, value in data.items()}
    if isinstance(data, list):
        return [expand_in_action(item) for item in data]
    if isinstance(data, tuple):
        return tuple(expand_in_action(item) for item in data)
    return data
