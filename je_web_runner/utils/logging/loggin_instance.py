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
                 maxBytes: int = 1073741824, backupCount: int = 0):
        """
        自訂日誌處理器，繼承 RotatingFileHandler
        Custom logging handler, inherits from RotatingFileHandler

        :param filename: 日誌檔案名稱 / log file name
        :param mode: 檔案開啟模式 (預設覆寫) / file open mode (default overwrite)
        :param maxBytes: 單一檔案最大大小 (預設 1GB) / max file size (default 1GB)
        :param backupCount: 保留的備份檔案數量 / number of backup files to keep
        """
        super().__init__(filename=filename, mode=mode, maxBytes=maxBytes, backupCount=backupCount)
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