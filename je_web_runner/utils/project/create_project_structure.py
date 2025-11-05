from os import getcwd
from pathlib import Path
from threading import Lock

from je_web_runner.utils.json.json_file.json_file import write_action_json
from je_web_runner.utils.project.template.template_executor import (
    executor_template_1,
    executor_template_2,
    bad_executor_template_1,
)
from je_web_runner.utils.project.template.template_keyword import (
    template_keyword_1,
    template_keyword_2,
    bad_template_1,
)


def create_dir(dir_name: str) -> None:
    """
    建立資料夾
    Create a directory

    :param dir_name: 要建立的資料夾名稱 / directory name to create
    """
    Path(dir_name).mkdir(
        parents=True,  # 若父層資料夾不存在則一併建立 / create parent dirs if not exist
        exist_ok=True  # 若資料夾已存在則不報錯 / no error if dir already exists
    )


def create_template(parent_name: str, project_path: str = None) -> None:
    """
    在專案目錄下建立範本檔案
    Create template files in the project directory

    :param parent_name: 專案名稱 / project name
    :param project_path: 專案建立路徑 (預設為當前工作目錄)
                         project path (default: current working directory)
    """
    if project_path is None:
        project_path = getcwd()

    keyword_dir_path = Path(project_path + "/" + parent_name + "/keyword")
    executor_dir_path = Path(project_path + "/" + parent_name + "/executor")
    lock = Lock()

    # 建立 keyword JSON 檔案
    # Create keyword JSON files
    if keyword_dir_path.exists() and keyword_dir_path.is_dir():
        write_action_json(project_path + "/" + parent_name + "/keyword/keyword1.json", template_keyword_1)
        write_action_json(project_path + "/" + parent_name + "/keyword/keyword2.json", template_keyword_2)
        write_action_json(project_path + "/" + parent_name + "/keyword/bad_keyword_1.json", bad_template_1)

    # 建立 executor Python 檔案
    # Create executor Python files
    if executor_dir_path.exists() and keyword_dir_path.is_dir():
        lock.acquire()
        try:
            with open(project_path + "/" + parent_name + "/executor/executor_one_file.py", "w+") as file:
                file.write(
                    executor_template_1.replace(
                        "{temp}",
                        project_path + "/" + parent_name + "/keyword/keyword1.json"
                    )
                )
            with open(project_path + "/" + parent_name + "/executor/executor_bad_file.py", "w+") as file:
                file.write(
                    bad_executor_template_1.replace(
                        "{temp}",
                        project_path + "/" + parent_name + "/keyword/bad_keyword_1.json"
                    )
                )
            with open(project_path + "/" + parent_name + "/executor/executor_folder.py", "w+") as file:
                file.write(
                    executor_template_2.replace(
                        "{temp}",
                        project_path + "/" + parent_name + "/keyword"
                    )
                )
        finally:
            lock.release()


def create_project_dir(project_path: str = None, parent_name: str = "WebRunner") -> None:
    """
    建立專案資料夾結構，並生成範本檔案
    Create project directory structure and generate template files

    :param parent_name: 專案名稱 / project name
    :param project_path: 專案建立路徑 (預設為當前工作目錄)
                         project path (default: current working directory)
    """
    if project_path is None:
        project_path = getcwd()

    # 建立 keyword 與 executor 資料夾
    # Create keyword and executor directories
    create_dir(project_path + "/" + parent_name + "/keyword")
    create_dir(project_path + "/" + parent_name + "executor")

    # 建立範本檔案
    # Create template files
    create_template(parent_name)