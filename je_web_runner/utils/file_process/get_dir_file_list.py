from os import getcwd, walk
from os.path import abspath, join
from typing import List


def get_dir_files_as_list(dir_path: str = getcwd(), default_search_file_extension: str = ".json") -> List[str]:
    """
    取得指定資料夾下所有符合副檔名的檔案清單
    Get all files in a directory that end with the given extension

    :param dir_path: 要搜尋的資料夾路徑 (預設為當前工作目錄)
                     Directory path to search (default: current working directory)
    :param default_search_file_extension: 要搜尋的副檔名 (預設為 ".json")
                                          File extension to search (default: ".json")
    :return: 若無符合則回傳空清單，否則回傳檔案完整路徑清單
             [] if no files found, otherwise [file1, file2, ...] with absolute paths
    """
    return [
        abspath(join(dir_path, file))  # 轉換為絕對路徑 / Convert to absolute path
        for root, dirs, files in walk(dir_path)  # 遍歷資料夾 / Walk through directory
        for file in files
        if file.endswith(default_search_file_extension.lower())  # 篩選符合副檔名的檔案 / Filter by extension
    ]