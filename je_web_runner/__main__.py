# argparse
import argparse
import json
import sys

from je_web_runner.utils.exception.exception_tags import argparse_get_wrong_data
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import execute_action
from je_web_runner.utils.executor.action_executor import execute_files
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.json.json_file.json_file import read_action_json

if __name__ == "__main__":
    try:
        # 處理單一檔案的執行
        # Execute actions from a single JSON file
        def preprocess_execute_action(file_path: str):
            execute_action(read_action_json(file_path))


        # 處理整個資料夾的執行
        # Execute actions from all JSON files in a directory
        def preprocess_execute_files(file_path: str):
            execute_files(get_dir_files_as_list(file_path))


        # 處理字串輸入的 JSON 執行
        # Execute actions from a JSON string
        def preprocess_read_str_execute_action(execute_str: str):
            if sys.platform in ["win32", "cygwin", "msys"]:
                # Windows 平台可能需要兩次 json.loads
                # On Windows, sometimes double json.loads is required
                json_data = json.loads(execute_str)
                execute_str = json.loads(json_data)
            else:
                execute_str = json.loads(execute_str)
            execute_action(execute_str)


        # 對應 argparse 參數與處理函式
        # Mapping argparse options to handler functions
        argparse_event_dict = {
            "execute_file": preprocess_execute_action,
            "execute_dir": preprocess_execute_files,
            "execute_str": preprocess_read_str_execute_action
        }

        # 建立 argparse 解析器
        parser = argparse.ArgumentParser()
        parser.add_argument("-e", "--execute_file", type=str, help="choose action file to execute")
        parser.add_argument("-d", "--execute_dir", type=str, help="choose dir include action file to execute")
        parser.add_argument("--execute_str", type=str, help="execute json str")

        # 解析參數
        args = parser.parse_args()
        args = vars(args)

        # 執行對應的處理函式
        for key, value in args.items():
            if value is not None:
                argparse_event_dict.get(key)(value)

        # 如果沒有任何參數，拋出例外
        if all(value is None for value in args.values()):
            raise WebRunnerExecuteException(argparse_get_wrong_data)

    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)