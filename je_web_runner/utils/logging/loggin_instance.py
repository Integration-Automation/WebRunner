"""
WebRunner 的 logger 與它寫入的日誌檔。
The ``WEBRunner`` logger and the file it writes to.

日誌檔是 ``$WEBRUNNER_LOG_PATH``（完整檔案路徑），否則 ``$WEBRUNNER_LOG_DIR/WEBRunner.log``，
都沒設就是 ``~/.je_web_runner/logs/WEBRunner.log``。相對路徑以 import 當下的工作目錄為準，
``os.devnull`` 會關掉檔案輸出。以前是相對路徑 ``WEBRunner.log``、import 時就開檔，所以任何 import
本套件的程式都會在當下的工作目錄留下一份日誌。
The log file is ``$WEBRUNNER_LOG_PATH`` (a full file path), else ``$WEBRUNNER_LOG_DIR/WEBRunner.log``,
else ``~/.je_web_runner/logs/WEBRunner.log``. A relative path resolves against the cwd at import time;
``os.devnull`` turns the file off. It used to be the relative ``WEBRunner.log``, opened at import, so
every process that imported the package left a log in whatever directory it started in.

套件自己的 handler 在第一筆紀錄才開檔（連同建立目錄），import 不寫任何檔案。同一個帳號的行程共用
這個檔，所以用附加模式、每行帶行程編號，而且只在開檔時輪替：Windows 上別的行程開著的檔案改不了名。
The package's handler opens the file (and creates its directory) on the first record, so importing
writes nothing. Processes of one account share the file, so it is opened for append, each line
carries the process id, and it is rotated only when opened: Windows refuses to rename a file another
process holds open.

模組路徑 ``je_web_runner.utils.logging.loggin_instance``（拼字照舊）與 ``web_runner_logger``、
``WebRunnerLoggingHandler`` 是公開的：Jeffrey_RPA 依賴它們（``architecture.md`` §6）。
The module path (misspelling kept), ``web_runner_logger`` and ``WebRunnerLoggingHandler`` are public:
Jeffrey_RPA relies on them (``architecture.md`` §6).
"""
import logging
import os
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 設定 root logger 的層級為 DEBUG（既有行為，宿主程式可能依賴，這次不動）
# Root logger at DEBUG: existing behaviour that host programs may rely on, left as it is.
logging.root.setLevel(logging.DEBUG)

# 建立一個名為 "WEBRunner" 的 logger，只輸出 WARNING 以上
# The "WEBRunner" logger, WARNING and above.
web_runner_logger = logging.getLogger("WEBRunner")
web_runner_logger.setLevel(logging.WARNING)

# 日誌格式：時間 | 行程編號 | logger 名稱 | 等級 | 訊息
# Log format: time | process id | logger name | level | message
formatter = logging.Formatter('%(asctime)s | %(process)d | %(name)s | %(levelname)s | %(message)s')

#: 指定日誌檔完整路徑的環境變數 / Environment variable naming the log file itself.
LOG_PATH_ENV = "WEBRUNNER_LOG_PATH"
#: 指定日誌目錄的環境變數 / Environment variable naming the directory for ``WEBRunner.log``.
LOG_DIR_ENV = "WEBRUNNER_LOG_DIR"
LOG_FILE_NAME = "WEBRunner.log"

#: 開檔時超過這個大小就先改名成 ``<name>.1`` / A file past this size is moved to ``<name>.1`` on open.
ROTATE_AT_BYTES = 10 * 1024 * 1024


def default_log_file() -> Path:
    """
    回傳日誌檔路徑：``$WEBRUNNER_LOG_PATH``、``$WEBRUNNER_LOG_DIR/WEBRunner.log``，否則家目錄下的預設位置。
    The log file: ``$WEBRUNNER_LOG_PATH``, else ``$WEBRUNNER_LOG_DIR/WEBRunner.log``, else the
    home-directory default ``~/.je_web_runner/logs/WEBRunner.log``.
    """
    configured = os.environ.get(LOG_PATH_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    directory = os.environ.get(LOG_DIR_ENV, "").strip()
    if directory:
        return Path(directory).expanduser() / LOG_FILE_NAME
    return Path.home() / ".je_web_runner" / "logs" / LOG_FILE_NAME


def _rotate_if_large(path: Path, limit: int) -> None:
    """
    檔案超過 ``limit`` 位元組就改名成 ``<path>.1``；別的行程開著時 Windows 會拒絕，就照舊附加。
    Move ``path`` to ``<path>.1`` when it is larger than ``limit`` bytes. Best effort: while another
    process holds the file Windows refuses the rename, and the file keeps growing.
    """
    try:
        if limit <= 0 or not path.is_file() or path.stat().st_size <= limit:
            return
        os.replace(path, path.with_name(path.name + ".1"))
    except OSError:
        return


class WebRunnerLoggingHandler(RotatingFileHandler):
    """
    WebRunner 的檔案 handler：預設寫到 ``default_log_file()``，附加模式，UTF-8。
    WebRunner's file handler: writes to ``default_log_file()``, appends, UTF-8.

    ``delay=True`` 讓開檔（連同建立目錄）延到第一筆紀錄；套件自己的 handler 就是這樣建的。開不了檔時
    改寫到 ``os.devnull`` 並發出一次 ``RuntimeWarning``，不讓記錄失敗。
    ``delay=True`` defers opening (and creating the directory) to the first record, which is how the
    package's own handler is built. A file that cannot be opened is swapped for ``os.devnull`` with one
    ``RuntimeWarning``.

    編碼必須明寫：沒有 ``encoding`` 時 ``logging`` 用平台的地區編碼（繁中 Windows 是 cp950），
    非 ASCII 的紀錄會變亂碼或整筆消失，而 Jeffrey_RPA 會把 UTF-8 的行 tee 進同一個檔。
    The encoding is explicit: without it ``logging`` uses the locale codec (cp950 on zh-TW Windows),
    so non-ASCII records turn to mojibake or vanish, and Jeffrey_RPA tees UTF-8 lines into the file.
    """

    def __init__(self, filename: str | None = None, mode: str = "a",
                 max_bytes: int = 0, backup_count: int = 0,
                 encoding: str = "utf-8", delay: bool = False) -> None:
        """
        :param filename: 日誌檔路徑，預設 ``default_log_file()`` / log file path, default ``default_log_file()``
        :param mode: 開檔模式（預設附加）/ file open mode (append by default)
        :param max_bytes: ``emit()`` 內輪替的門檻，0 表示只在開檔時輪替 / in-``emit()`` rotation size, 0 = only on open
        :param backup_count: 保留的備份數 / number of backups to keep
        :param encoding: 檔案編碼，預設 UTF-8 / file encoding, UTF-8 by default
        :param delay: 延到第一筆紀錄才開檔 / open the file on the first record
        """
        path = filename if filename is not None else str(default_log_file())
        super().__init__(filename=path, mode=mode, maxBytes=max_bytes, backupCount=backup_count,
                         encoding=encoding, delay=delay, errors="backslashreplace")
        self.setFormatter(formatter)
        self.setLevel(logging.DEBUG)

    def _open(self):
        """
        開檔前先建立目錄並輪替；開不了就改寫到 ``os.devnull``，只警告一次。
        Create the directory and rotate before opening; fall back to ``os.devnull``, warning once.
        """
        path = Path(self.baseFilename)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _rotate_if_large(path, ROTATE_AT_BYTES)
            return super()._open()
        except OSError as error:
            warnings.warn(f"WebRunner log file {path} unavailable, file logging off: {error!r}",
                          RuntimeWarning, stacklevel=2)
            # handler 自己持有並關閉這個串流 / the handler owns and closes this stream
            return open(os.devnull, self.mode, encoding=self.encoding, errors=self.errors)  # noqa: SIM115


# 建立檔案處理器（第一筆紀錄才開檔）並加入 logger
# The package's file handler, opened on the first record.
file_handler = WebRunnerLoggingHandler(delay=True)
web_runner_logger.addHandler(file_handler)
