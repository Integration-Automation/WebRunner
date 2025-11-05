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
    try:
        lock.acquire()
        file_path = Path(json_file_path)
        if file_path.exists() and file_path.is_file():
            with open(json_file_path, encoding="utf-8") as read_file:
                return json.load(read_file)
        else:
            # 如果檔案不存在或不是檔案，拋出例外
            # Raise exception if file does not exist or is not a file
            raise WebRunnerJsonException(cant_find_json_error)
    except WebRunnerJsonException:
        raise WebRunnerJsonException(cant_find_json_error)
    finally:
        lock.release()


def write_action_json(json_save_path: str, action_json: list):
    """
    寫入 JSON 動作檔案
    Write the action JSON file

    :param json_save_path: JSON 儲存路徑 / path to save the JSON file
    :param action_json: 要寫入的 JSON 資料 (list) / JSON data to write (list)
    """
    try:
        lock.acquire()
        with open(json_save_path, "w+", encoding="utf-8") as file_to_write:
            file_to_write.write(json.dumps(action_json, indent=4, ensure_ascii=False))
    except WebRunnerJsonException:
        raise WebRunnerJsonException(cant_save_json_error)
    finally:
        lock.release()