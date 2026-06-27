import json
from pathlib import Path
from threading import Lock

from je_web_runner.utils.exception.exception_tags import cant_find_json_error, cant_save_json_error
from je_web_runner.utils.exception.exceptions import WebRunnerJsonException

# 全域 Lock，避免多執行緒同時存取檔案
# Global lock to prevent concurrent file access in multi-threaded environments
lock = Lock()


def read_action_json(json_file_path: str) -> list:
    """
    讀取 JSON 動作檔案
    Read the action JSON file

    :param json_file_path: JSON 檔案路徑 / path to the JSON file
    :return: JSON 內容 (list) / JSON content as list
    """
    file_path = Path(json_file_path)
    if not (file_path.exists() and file_path.is_file()):
        # 檔案不存在或不是檔案
        # File does not exist or is not a file
        raise WebRunnerJsonException(cant_find_json_error)
    with lock, open(json_file_path, encoding="utf-8") as read_file:
        return json.load(read_file)


def write_action_json(json_save_path: str, action_json: list):
    """
    寫入 JSON 動作檔案
    Write the action JSON file

    :param json_save_path: JSON 儲存路徑 / path to save the JSON file
    :param action_json: 要寫入的 JSON 資料 (list) / JSON data to write (list)
    """
    try:
        with lock, open(json_save_path, "w", encoding="utf-8") as file_to_write:
            file_to_write.write(json.dumps(action_json, indent=4, ensure_ascii=False))
    except (OSError, TypeError, ValueError) as error:
        # 先前 except 只攔 WebRunnerJsonException(本體不會丟)，等於沒處理 —
        # 寫檔/序列化失敗會以原生 OSError 外漏。改為包成 cant_save_json_error。
        raise WebRunnerJsonException(cant_save_json_error) from error