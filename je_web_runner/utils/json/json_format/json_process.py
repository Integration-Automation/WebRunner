import json.decoder
import sys
from json import dumps, loads

from je_web_runner.utils.exception.exception_tags import wrong_json_data_error, cant_reformat_json_error
from je_web_runner.utils.exception.exceptions import WebRunnerJsonException


def __process_json(json_string: str, **kwargs) -> str:
    """
    將 JSON 字串重新格式化
    Reformat a JSON string

    :param json_string: 完整 JSON 字串 (不是 dict/list，而是 str)
                        Full JSON string (not dict/list, but str)
    :param kwargs: 傳遞給 json.dumps 的額外參數
                   Extra kwargs for json.dumps
    :return: 格式化後的 JSON 字串
             Reformatted JSON string
    """
    try:
        # 嘗試將字串解析成 JSON，再重新格式化輸出
        # Try to parse string into JSON, then reformat
        return dumps(loads(json_string), indent=4, sort_keys=True, **kwargs)
    except json.JSONDecodeError as error:
        # 如果 JSON 格式錯誤，輸出錯誤訊息並拋出例外
        # If JSON is invalid, print error and raise exception
        print(wrong_json_data_error, file=sys.stderr)
        raise error
    except TypeError:
        # 如果傳入的不是字串，而是 Python 物件，直接嘗試格式化
        # If input is not string but Python object, try formatting directly
        try:
            return dumps(json_string, indent=4, sort_keys=True, **kwargs)
        except TypeError:
            # 如果仍然失敗，拋出自訂例外
            # If still fails, raise custom exception
            raise WebRunnerJsonException(wrong_json_data_error)


def reformat_json(json_string: str, **kwargs) -> str:
    """
    對外公開的 JSON 格式化函式
    Public function to reformat JSON string

    :param json_string: 合法的 JSON 字串
                        Valid JSON string
    :param kwargs: 傳遞給 __process_json 的參數
                   Parameters passed to __process_json
    :return: 格式化後的 JSON 字串
             Reformatted JSON string
    """
    try:
        return __process_json(json_string, **kwargs)
    except WebRunnerJsonException:
        # 如果內部處理失敗，統一拋出「無法重新格式化 JSON」的錯誤
        # If processing fails, raise unified "cannot reformat JSON" exception
        raise WebRunnerJsonException(cant_reformat_json_error)