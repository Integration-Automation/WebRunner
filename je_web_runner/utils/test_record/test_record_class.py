import datetime
from typing import Union

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TestRecord(object):
    """
    測試紀錄管理器
    Test record manager
    """

    def __init__(self, init_record: bool = False):
        # 儲存所有測試紀錄的清單
        # List to store all test records
        self.test_record_list: list = list()

        # 是否啟用紀錄功能
        # Flag to enable/disable recording
        self.init_record: bool = init_record

    def clean_record(self) -> None:
        """
        清空所有測試紀錄
        Clear all test records
        """
        self.test_record_list = list()

    def set_record_enable(self, set_enable: bool = True):
        """
        開啟或關閉紀錄功能
        Enable or disable recording

        :param set_enable: True = 開啟紀錄, False = 關閉紀錄
                           True = enable recording, False = disable recording
        """
        web_runner_logger.info(f"set_record_enable, set_enable: {set_enable}")
        self.init_record = set_enable


# 全域單例，用來管理測試紀錄
# Global singleton instance to manage test records
test_record_instance = TestRecord()


def record_action_to_list(function_name: str,
                          local_param: Union[dict, None],
                          program_exception: Union[Exception, None] = None):
    """
    將一次函式呼叫紀錄到 test_record_list
    Record a function call into test_record_list

    :param function_name: 呼叫的函式名稱 / name of the function being called
    :param local_param: 呼叫時使用的參數 (dict) / parameters used in the call (dict)
    :param program_exception: 執行過程中發生的例外 (若有) / exception occurred during execution (if any)
    """
    if not test_record_instance.init_record:
        # 若未啟用紀錄，則直接跳過
        # Skip if recording is disabled
        return
    else:
        test_record_instance.test_record_list.append({
            "function_name": function_name,
            "local_param": local_param,
            "time": str(datetime.datetime.now()),
            "program_exception": repr(program_exception)
        })
