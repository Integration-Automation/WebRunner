from importlib import import_module
from importlib.util import find_spec
from inspect import getmembers, isfunction, isbuiltin, isclass
from sys import stderr

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class PackageManager(object):

    def __init__(self):
        # 已安裝套件快取，避免重複載入
        # Cache of installed packages to avoid re-importing
        self.installed_package_dict = {}

        # 目標執行器 (Executor / CallbackExecutor)
        # Target executors (Executor / CallbackExecutor)
        self.executor = None
        self.callback_executor = None

    def check_package(self, package: str) -> str | None:
        """
        檢查套件是否存在，若存在則載入並快取
        Check if a package exists, import it if found, and cache it

        :param package: 套件名稱 / package name
        :return: 套件模組物件，若不存在則回傳 None
                 Package module object if found, else None
        """
        if self.installed_package_dict.get(package, None) is None:
            found_spec = find_spec(package)
            if found_spec is not None:
                try:
                    installed_package = import_module(found_spec.name)
                    self.installed_package_dict.update(
                        {found_spec.name: installed_package}
                    )
                except ModuleNotFoundError as error:
                    print(repr(error), file=stderr)
        return self.installed_package_dict.get(package, None)

    def add_package_to_executor(self, package):
        """
        將套件的成員加入到 executor 的 event_dict
        Add package members into executor's event_dict

        :param package: 套件名稱 / package name
        """
        web_runner_logger.info(f"add_package_to_executor, package: {package}")
        self.add_package_to_target(
            package=package,
            target=self.executor
        )

    def add_package_to_callback_executor(self, package):
        """
        將套件的成員加入到 callback_executor 的 event_dict
        Add package members into callback_executor's event_dict

        :param package: 套件名稱 / package name
        """
        web_runner_logger.info(f"add_package_to_callback_executor, package: {package}")
        self.add_package_to_target(
            package=package,
            target=self.callback_executor
        )

    def get_member(self, package, predicate, target):
        """
        取得套件成員並加入到目標 event_dict
        Get members of a package and add them into target's event_dict

        :param package: 套件名稱 / package name
        :param predicate: 過濾條件 (isfunction, isbuiltin, isclass)
                          Predicate (isfunction, isbuiltin, isclass)
        :param target: 目標執行器 (executor 或 callback_executor)
                       Target executor (executor or callback_executor)
        """
        installed_package = self.check_package(package)
        if installed_package is not None and target is not None:
            for member in getmembers(installed_package, predicate):
                target.event_dict.update(
                    {str(package) + "_" + str(member[0]): member[1]}
                )
        elif installed_package is None:
            print(repr(ModuleNotFoundError(f"Can't find package {package}")), file=stderr)
        else:
            print(f"Executor error {self.executor}", file=stderr)

    def add_package_to_target(self, package, target):
        """
        將套件的 function、builtin、class 成員加入到指定 target
        Add functions, builtins, and classes of a package into target

        :param package: 套件名稱 / package name
        :param target: 目標執行器 / target executor
        """
        try:
            self.get_member(package=package, predicate=isfunction, target=target)
            self.get_member(package=package, predicate=isbuiltin, target=target)
            self.get_member(package=package, predicate=isclass, target=target)
        except Exception as error:
            print(repr(error), file=stderr)


# 建立全域 PackageManager 實例
# Create global PackageManager instance
package_manager: PackageManager = PackageManager()