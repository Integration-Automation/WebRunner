import json
from threading import Lock

from je_web_runner.utils.exception.exception_tags import cant_generate_json_report
from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


def generate_json():
    """
    產生測試結果的 JSON 結構
    Generate JSON structure for test results

    :return: (success_dict, failure_dict)
             成功與失敗的測試紀錄字典
             Dictionaries of success and failure test records
    """
    web_runner_logger.info("generate_json")

    # 如果沒有任何測試紀錄與錯誤紀錄，拋出例外
    # Raise exception if no test or error records exist
    if len(test_record_instance.test_record_list) == 0 and len(test_record_instance.error_record_list) == 0:
        raise WebRunnerGenerateJsonReportException(cant_generate_json_report)
    else:
        success_dict = dict()
        failure_dict = dict()

        # 計數器與前綴字串
        # Counters and prefix strings
        failure_count: int = 1
        failure_test_str: str = "Failure_Test"
        success_count: int = 1
        success_test_str: str = "Success_Test"

        # 遍歷測試紀錄
        # Iterate through test records
        for record_data in test_record_instance.test_record_list:
            if record_data.get("program_exception", "None") == "None":
                # 成功紀錄
                # Success record
                success_dict.update(
                    {
                        success_test_str + str(success_count): {
                            "function_name": str(record_data.get("function_name")),
                            "param": str(record_data.get("local_param")),
                            "time": str(record_data.get("time")),
                            "exception": str(record_data.get("program_exception")),
                        }
                    }
                )
                success_count += 1
            else:
                # 失敗紀錄
                # Failure record
                failure_dict.update(
                    {
                        failure_test_str + str(failure_count): {
                            "function_name": str(record_data.get("function_name")),
                            "param": str(record_data.get("local_param")),
                            "time": str(record_data.get("time")),
                            "exception": str(record_data.get("program_exception")),
                        }
                    }
                )
                failure_count += 1

    return success_dict, failure_dict


def generate_json_report(json_file_name: str = "default_name"):
    """
    產生並輸出 JSON 測試報告
    Generate and save JSON test reports

    :param json_file_name: 輸出檔案名稱 (不含副檔名)
                           Output file name (without extension)
    """
    web_runner_logger.info(f"generate_json_report, json_file_name: {json_file_name}")
    lock = Lock()

    # 取得成功與失敗紀錄
    # Get success and failure records
    success_dict, failure_dict = generate_json()

    # 輸出成功紀錄
    # Write success records
    try:
        lock.acquire()
        with open(json_file_name + "_success.json", "w+") as file_to_write:
            json.dump(dict(success_dict), file_to_write, indent=4)
    except Exception as error:
        web_runner_logger.error(f"generate_json_report, json_file_name: {json_file_name}, failed: {repr(error)}")
    finally:
        lock.release()

    # 輸出失敗紀錄
    # Write failure records
    try:
        lock.acquire()
        with open(json_file_name + "_failure.json", "w+") as file_to_write:
            json.dump(dict(failure_dict), file_to_write, indent=4)
    except Exception as error:
        web_runner_logger.error(f"generate_json_report, json_file_name: {json_file_name}, failed: {repr(error)}")
    finally:
        lock.release()