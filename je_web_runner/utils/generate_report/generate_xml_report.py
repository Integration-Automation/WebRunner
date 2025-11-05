from threading import Lock
from xml.dom.minidom import parseString

from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.xml.change_xml_structure.change_xml_structure import dict_to_elements_tree


def generate_xml():
    """
    產生 XML 結構字串
    Generate XML structure strings

    :return: (success_xml_str, failure_xml_str)
             成功與失敗的 XML 結構字串
             XML strings for success and failure test results
    """
    web_runner_logger.info("generate_xml")

    # 從 JSON 報告生成器取得成功與失敗的測試紀錄
    # Get success and failure test records from JSON generator
    success_dict, failure_dict = generate_json()

    # 包裝成 XML 根節點
    # Wrap into XML root node
    success_dict = {"xml_data": success_dict}
    failure_dict = {"xml_data": failure_dict}

    # 轉換 dict -> XML 結構
    # Convert dict -> XML structure
    success_json_to_xml = dict_to_elements_tree(success_dict)
    failure_json_to_xml = dict_to_elements_tree(failure_dict)

    return success_json_to_xml, failure_json_to_xml


def generate_xml_report(xml_file_name: str = "default_name"):
    """
    產生並輸出 XML 測試報告
    Generate and save XML test reports

    :param xml_file_name: 輸出檔案名稱 (不含副檔名)
                          Output file name (without extension)
    """
    web_runner_logger.info(f"generate_xml_report, xml_file_name: {xml_file_name}")

    # 取得成功與失敗的 XML 結構
    # Get success and failure XML structures
    success_xml, failure_xml = generate_xml()

    # 使用 minidom 美化輸出
    # Beautify XML output using minidom
    success_xml = parseString(success_xml).toprettyxml()
    failure_xml = parseString(failure_xml).toprettyxml()

    lock = Lock()

    # 輸出失敗報告
    # Write failure report
    try:
        lock.acquire()
        with open(xml_file_name + "_failure.xml", "w+") as file_to_write:
            file_to_write.write(failure_xml)
    except Exception as error:
        web_runner_logger.error(f"generate_xml_report, xml_file_name: {xml_file_name}, failed: {repr(error)}")
    finally:
        lock.release()

    # 輸出成功報告
    # Write success report
    try:
        lock.acquire()
        with open(xml_file_name + "_success.xml", "w+") as file_to_write:
            file_to_write.write(success_xml)
    except Exception as error:
        web_runner_logger.error(f"generate_xml_report, xml_file_name: {xml_file_name}, failed: {repr(error)}")
    finally:
        lock.release()