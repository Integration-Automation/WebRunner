import builtins
import time
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException, WebRunnerAddCommandException
from je_web_runner.utils.executor._event_table import build_event_dict
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# 禁止暴露於 JSON 動作執行器的內建函式，避免任意程式碼執行
# 只註冊允許清單，不再用黑名單：「除了危險的以外全部註冊」會讓 action JSON 拿到
# 未來 Python 新增的任何內建函式，而且原本的黑名單仍放行 dir / hasattr / id /
# isinstance / iter / next。這份清單與 MailThunder、LoadDensity 的相同，所以同一份
# action list 在工作區各框架的行為一致（工作區 progress.md X-12）。
# An allowlist, not a blocklist: "register everything except the dangerous ones"
# hands action JSON whatever a future Python adds to builtins, and the previous
# list still let dir / hasattr / id / isinstance / iter / next through. The names
# match MailThunder's and LoadDensity's, so one action list behaves the same
# across the workspace's frameworks (workspace progress.md X-12).
SAFE_BUILTINS = frozenset({
    "abs", "all", "any", "ascii", "bin", "callable", "chr", "divmod",
    "format", "hash", "hex", "len", "max", "min", "oct", "ord", "pow",
    "print", "repr", "round", "sorted", "sum",
})

# WR_* 命令會把整段 JavaScript 字串送進瀏覽器執行；當 action JSON 來源不可信時
# 必須能關閉。透過 ``set_allow_arbitrary_script(False)`` 切換。
# WR_* commands that hand a JS string straight to the browser. When action
# JSON comes from an untrusted source the operator should be able to disable
# them; ``set_allow_arbitrary_script(False)`` flips the gate.
_ARBITRARY_SCRIPT_COMMANDS = frozenset({
    "WR_execute_script",
    "WR_execute_async_script",
    "WR_pw_evaluate",
    "WR_cdp",
    "WR_pw_cdp",
    "WR_execute_cdp_cmd",
    "WR_add_script_to_evaluate_on_new_document",
})


def _try_selenium_screenshot() -> bytes | None:
    try:
        if webdriver_wrapper_instance.current_webdriver is None:
            return None
        return webdriver_wrapper_instance.get_screenshot_as_png()
    except Exception:
        return None


def _try_playwright_screenshot() -> bytes | None:
    try:
        if not _pw.playwright_wrapper_instance._pages:
            return None
        return _pw.playwright_wrapper_instance.screenshot_bytes()
    except Exception:
        return None


class Executor:

    def __init__(self):
        # 失敗時自動截圖目錄；None 代表停用
        # Output directory for auto-captured failure screenshots; None disables it.
        self.failure_screenshot_dir: str | None = None
        # 全域重試策略 (預設關閉)
        # Global retry policy. retries == 0 disables retry; backoff is in
        # seconds and is multiplied by the (1-based) attempt number.
        self.retry_policy = {"retries": 0, "backoff": 0.0}
        # 是否允許將任意 JS / CDP 字串透過 action 送到瀏覽器；預設 True 維持向下
        # 相容，但若 action JSON 來自不可信來源請改 False。
        # Default True for back-compat; flip to False when action JSON comes
        # from an untrusted source.
        self.allow_arbitrary_script: bool = True
        # Optional context-manager factory invoked once per action so an
        # observability stack (OpenTelemetry, custom logging, …) can wrap
        # each call without the executor depending on the SDK directly.
        self._action_span_factory: Callable[[str], Any] | None = None
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        self.event_dict = build_event_dict(self)

        # 只把允許清單裡的內建函式加入事件字典
        # Register only the allowlisted builtins.
        for name in sorted(SAFE_BUILTINS):
            self.event_dict[name] = getattr(builtins, name)

    def set_retry_policy(self, retries: int = 0, backoff: float = 0.0) -> None:
        """
        設定全域重試策略
        Configure the global retry policy. ``retries`` is the number of extra
        attempts after the first; ``backoff`` is base seconds between attempts
        (multiplied by the attempt index, so 0.5 → 0.5s, 1.0s, 1.5s …).
        """
        self.retry_policy = {"retries": max(int(retries), 0), "backoff": max(float(backoff), 0.0)}

    def set_action_span_factory(self, factory: Callable[[str], Any] | None) -> None:
        """
        登錄一個 context-manager factory，每個 action 會被它包起來
        Register an optional ``ContextManager`` factory invoked once per
        action; pass ``None`` to disable.
        """
        self._action_span_factory = factory

    def _execute_with_retry(self, action):
        """Run ``_execute_event`` honouring the global retry policy."""
        if self._action_span_factory is not None and isinstance(action, list) and action:
            with self._action_span_factory(str(action[0])):
                return self._do_with_retry(action)
        return self._do_with_retry(action)

    def _do_with_retry(self, action):
        retries = int(self.retry_policy.get("retries", 0))
        backoff = float(self.retry_policy.get("backoff", 0.0))
        for attempt in range(retries + 1):
            try:
                return self._execute_event(action)
            except Exception as error:
                if attempt >= retries:
                    raise
                if backoff > 0:
                    time.sleep(backoff * (attempt + 1))
                web_runner_logger.warning(
                    f"action {action!r} failed on attempt {attempt + 1}, retrying: {error!r}"
                )
        # Unreachable: ``range(retries + 1)`` always has at least one iteration.
        raise WebRunnerExecuteException("retry loop exited without resolution")

    def set_failure_screenshot_dir(self, path: str | None) -> None:
        """
        設定 (或停用) 動作失敗時的自動截圖目錄
        Configure the directory used for auto-screenshots on action failure.
        Pass ``None`` to disable.
        """
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)
        self.failure_screenshot_dir = path

    def _capture_failure_screenshot(self, action) -> str | None:
        """Best-effort screenshot save when an action raises. Returns path or None."""
        if not self.failure_screenshot_dir:
            return None
        png = _try_selenium_screenshot() or _try_playwright_screenshot()
        if not png:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        raw_name = str(action[0] if isinstance(action, list) and action else "unknown")
        # Strip any path separators and limit to safe characters; otherwise an
        # action JSON could ship a command name like ``../../etc/passwd`` and
        # cause a path traversal write (SonarCloud S2083).
        safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in "-_")[:64] or "unknown"
        base_dir = Path(self.failure_screenshot_dir).resolve()
        target = (base_dir / f"{timestamp}_{safe_name}.png").resolve()
        # Belt-and-braces: confirm the resolved path stays inside the
        # configured directory before writing.
        try:
            target.relative_to(base_dir)
        except ValueError:
            web_runner_logger.error(
                f"failure screenshot path escapes configured dir: {target!r}"
            )
            return None
        try:
            target.write_bytes(png)
            return str(target)
        except OSError as error:
            web_runner_logger.error(f"failure screenshot write failed: {error!r}")
            return None

    def set_allow_arbitrary_script(self, enabled: bool) -> None:
        """
        切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令
        Toggle the gate for arbitrary-script commands. Disable when action
        JSON files are not fully trusted.
        """
        self.allow_arbitrary_script = bool(enabled)

    @staticmethod
    def set_allow_arbitrary_packages(enabled: bool) -> None:
        """
        允許或拒絕載入允許清單以外的套件（``WR_add_package_to_executor``）
        Allow (True) or refuse (False) ``WR_add_package_to_executor`` for packages outside
        the allowlist. Python only, never an action command, so an action file cannot open
        its own gate. Until it is called, any package loads with a ``DeprecationWarning``.
        """
        package_manager.set_allow_arbitrary_packages(enabled)

    @staticmethod
    def allow_packages(*packages: str) -> None:
        """
        把套件（連同子模組）加入 ``WR_add_package_to_executor`` 的允許清單
        Add packages, and their submodules, to the allowlist of ``WR_add_package_to_executor``.
        """
        package_manager.allow_packages(*packages)

    def _execute_event(self, action: list):
        """
        執行事件字典中的函式
        Execute a function from event_dict

        :param action: 指令清單，例如 ["函式名稱", {參數}] 或 ["函式名稱"]
                       Action list, e.g., ["function_name", {params}] or ["function_name"]
        :return: 執行結果 / return value of the executed function
        """
        if action[0] in _ARBITRARY_SCRIPT_COMMANDS and not self.allow_arbitrary_script:
            raise WebRunnerExecuteException(
                f"arbitrary-script command {action[0]!r} is disabled; "
                "call WR_set_allow_arbitrary_script(true) to enable"
            )
        event = self.event_dict.get(action[0])
        if event is None:
            raise WebRunnerExecuteException(executor_data_error + " unknown command: " + str(action[0]))
        if len(action) == 1:
            # 無參數呼叫
            # Call without arguments
            return event()
        if len(action) == 2:
            if isinstance(action[1], dict):
                # 關鍵字參數呼叫
                # Call with keyword arguments
                return event(**action[1])
            # 位置參數呼叫
            # Call with positional arguments
            return event(*action[1])
        if len(action) == 3:
            # 同時帶位置 + 關鍵字參數
            # Mixed positional + keyword arguments
            positional, kwargs = action[1], action[2]
            if not isinstance(positional, (list, tuple)) or not isinstance(kwargs, dict):
                raise WebRunnerExecuteException(
                    f"{executor_data_error}: 3-element action requires [cmd, [positional], {{kwargs}}]"
                )
            return event(*positional, **kwargs)
        # 格式錯誤，拋出例外
        # Invalid format, raise exception
        raise WebRunnerExecuteException(executor_data_error + " " + str(action))

    def execute_action(self, action_list: list | dict) -> dict:
        """
        執行一系列動作
        Execute a list of actions

        :param action_list: 動作清單，例如：
           Action list, e.g.:
           [
               ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
               ["WR_to_url", {"url": "https://www.google.com"}],
               ["WR_quit"]
           ]
        :return: 執行紀錄字典 {動作描述: 回傳值}
                 Execution record dict {action: response}
        """
        execute_record_dict, _failed = self.collect_action_results(action_list)

        # 輸出執行結果
        # Print execution results
        for key, value in execute_record_dict.items():
            print(key)
            print(value)

        return execute_record_dict

    def collect_action_results(self, action_list: list | dict) -> tuple[dict, list[str]]:
        """
        執行動作清單但不印出；另外回傳失敗動作的紀錄鍵
        Run ``action_list`` exactly like :meth:`execute_action` but print nothing.

        :return: ``(record, failed)``: the record dict ``execute_action`` returns, and the record
                 keys of the actions that raised (their record value is the error's ``repr``).
        :raises WebRunnerExecuteException: when ``action_list`` is not a list, or a dict
                 without a ``webdriver_wrapper`` list.
        """
        web_runner_logger.info(f"execute_action, action_list: {action_list}")
        action_list = self._action_list_of(action_list)
        execute_record_dict = {}
        failed = []
        for action in action_list:
            execute_record = "execute: " + str(action)
            try:
                execute_record_dict.update({execute_record: self._execute_with_retry(action)})
            except Exception as error:  # every command's own failure is recorded, not raised
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"action: {action}, failed: {error!r}")
                execute_record_dict.update({execute_record: self._failure_text(action, error)})
                failed.append(execute_record)
        return execute_record_dict, failed

    @staticmethod
    def _action_list_of(action_list: list | dict) -> list:
        # 如果傳入的是 dict，則嘗試取出 "webdriver_wrapper" 的動作清單；結果必須是 list
        # A dict must carry its actions under "webdriver_wrapper"; the result must be a list
        # (a string would otherwise be iterated character by character).
        if type(action_list) is dict:
            action_list = action_list.get("webdriver_wrapper", None)
        if not isinstance(action_list, list):
            web_runner_logger.error(
                f"execute_action, action_list: {action_list}, "
                f"failed: {WebRunnerExecuteException(executor_list_error)}")
            raise WebRunnerExecuteException(executor_list_error)
        return action_list

    def _failure_text(self, action, error: Exception) -> str:
        screenshot_path = self._capture_failure_screenshot(action)
        if screenshot_path:
            return f"{error!r} (failure screenshot: {screenshot_path})"
        return repr(error)

    def execute_files(self, execute_files_list: list) -> list:
        """
        從檔案載入並執行動作
        Execute actions from files

        :param execute_files_list: 檔案路徑清單 / list of file paths
        :return: 每個檔案的執行結果清單 / list of execution results
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        execute_detail_list = []
        for file in execute_files_list:
            # 讀取 JSON 檔案並執行
            # Read JSON file and execute
            execute_detail_list.append(self.execute_action(read_action_json(file)))
        return execute_detail_list


# 建立全域 Executor 實例
# Create global Executor instance
executor = Executor()
package_manager.executor = executor

def add_command_to_executor(command_dict: dict):
    """
    動態新增指令到 Executor
    Dynamically add commands to Executor

    :param command_dict: {指令名稱: 函式} / {command_name: function}
    """
    for command_name, command in command_dict.items():
        if isinstance(command, (types.MethodType, types.FunctionType)):
            executor.event_dict.update({command_name: command})
        else:
            raise WebRunnerAddCommandException(add_command_exception_tag)

def execute_action(action_list: list) -> dict:
    """
    全域方法：執行動作清單
    Global method: execute action list
    """
    return executor.execute_action(action_list)

def execute_files(execute_files_list: list) -> list:
    """
    全域方法：執行檔案中的動作
    Global method: execute actions from files
    """
    return executor.execute_files(execute_files_list)
