import logging
from logging.handlers import RotatingFileHandler

# 設定 root logger 的層級為 DEBUG
# Set root logger level to DEBUG
logging.root.setLevel(logging.DEBUG)

# 建立一個名為 "WEBRunner" 的 logger
# Create a logger named "WEBRunner"
web_runner_logger = logging.getLogger("WEBRunner")

# 設定 logger 的層級為 WARNING (只會輸出 WARNING 以上的訊息)
# Set logger level to WARNING (only WARNING and above will be logged)
web_runner_logger.setLevel(logging.WARNING)

# 定義日誌輸出格式
# Define log output format
formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')


class WebRunnerLoggingHandler(RotatingFileHandler):
    def __init__(self, filename: str = "WEBRunner.log", mode="w",
                 max_bytes: int = 1073741824, backup_count: int = 0,
                 encoding: str = "utf-8"):
        """
        自訂日誌處理器，繼承 RotatingFileHandler
        Custom logging handler, inherits from RotatingFileHandler

        :param filename: 日誌檔案名稱 / log file name
        :param mode: 檔案開啟模式 (預設覆寫) / file open mode (default overwrite)
        :param max_bytes: 單一檔案最大大小 (預設 1GB) / max file size (default 1GB)
        :param backup_count: 保留的備份檔案數量 / number of backup files to keep
        :param encoding: 日誌檔編碼，預設 UTF-8 / log file encoding, defaults to UTF-8

        編碼必須明寫。沒有 ``encoding`` 時 ``logging`` 會用平台的地區編碼開檔
        (Windows 繁中環境是 cp950)，於是同一個日誌檔可能同時存在兩種編碼：
        本函式庫寫的行是 cp950，而呼叫端 tee 進去的行是 UTF-8。今天訊息全是
        英文所以看不出來，但只要有一行帶非 ASCII 字元就會落地成亂碼，
        而且只有那一行壞、其餘完全正常，非常難追。

        The encoding must be stated explicitly. Without ``encoding``,
        ``logging`` opens the file with the platform's locale codec (cp950 on
        a Traditional-Chinese Windows box), so one log file can end up holding
        two encodings at once -- lines written by this library in cp950, lines
        tee'd in by the caller in UTF-8. It is invisible while every message is
        ASCII, but the first non-ASCII line lands as mojibake, and only that
        line breaks, which makes it very hard to track down.
        """
        super().__init__(filename=filename, mode=mode, maxBytes=max_bytes,
                         backupCount=backup_count, encoding=encoding)
        self.formatter = formatter  # 設定日誌格式 / set log formatter
        self.setLevel(logging.DEBUG)  # 設定 handler 層級為 DEBUG / set handler level to DEBUG

    def emit(self, record: logging.LogRecord) -> None:
        """
        覆寫 emit 方法，但目前僅呼叫父類別的 emit
        Override emit method, currently just calls parent emit
        """
        super().emit(record)


# 建立檔案處理器並加入 logger
# Create file handler and add to logger
file_handler = WebRunnerLoggingHandler()
web_runner_logger.addHandler(file_handler)