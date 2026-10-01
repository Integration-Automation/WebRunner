"""
WebRunner 的動作執行器，建在 je_action_core 上
The action executor, built on je_action_core's :class:`~je_action_core.ActionExecutor`.

The core runs the list, keys the records (``execute: <action>``, repeats numbered ``#2`` …), prints them and
holds the commands. WebRunner adds its dialect: ``[name, [args], {kwargs}]`` actions, refused commands and the
arbitrary-script gate (checked before the name is looked up), the retry policy and the action span (around
every action, through :meth:`Executor.attempt`), failure screenshots and traces in the failure record, and
:meth:`Executor.execute_one`.
"""
import contextlib
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from je_action_core import (
    SAFE_BUILTINS,
    ActionExecutor,
    BoundAction,
    CommandPolicy,
    CommandRegistry,
    DuplicateKeys,
    ExecutorSettings,
    PrintReporter,
    safe_builtin_commands,
    unique_record_key,
)

from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import (
    WebRunnerAddCommandException,
    WebRunnerExecuteException,
    describe_error,
)
from je_web_runner.utils.executor._event_table import build_event_dict
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_record.wrapper_failures import set_raise_wrapper_errors
from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# 只註冊允許清單裡的內建函式（je_action_core 的 SAFE_BUILTINS，與 MailThunder、LoadDensity 相同）
# Only the allowlisted builtins are registered: je_action_core's SAFE_BUILTINS, the list MailThunder and
# LoadDensity use too, so one action list behaves the same across the workspace's frameworks (workspace
# progress.md X-12). An allowlist, because "everything except the dangerous ones" would hand action JSON
# whatever a future Python adds to builtins. Re-exported here: ``SAFE_BUILTINS`` and ``unique_record_key``
# keep their import path in this module.
__all__ = [
    "SAFE_BUILTINS", "Executor", "add_command_to_executor", "execute_action", "execute_files", "execute_one",
    "executor", "unique_record_key",
]

_NAME_ONLY = 1
_NAME_AND_PAYLOAD = 2
_NAME_ARGS_AND_KWARGS = 3

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
    "WR_pw_add_init_script",
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


@dataclass(frozen=True)
class _ActionParser:
    """
    WebRunner 的動作格式
    ``[name]``, ``[name, {kwargs}]``, ``[name, [args]]`` or ``[name, [args], {kwargs}]``. The name is looked
    up first. An unknown name, a three-element action of any other shape and a longer action raise
    :class:`WebRunnerExecuteException`; an empty action raises ``IndexError``.
    """

    def bind(self, action: Any, resolve: Callable[[Any], Callable[..., Any] | None]) -> BoundAction:
        """Bind ``action`` to the command ``resolve`` finds for its name."""
        name = action[0]
        command = resolve(name)
        if command is None:
            raise WebRunnerExecuteException(f"{executor_data_error} unknown command: {name!s}")
        if len(action) == _NAME_ONLY:
            return BoundAction(name, command)
        if len(action) == _NAME_AND_PAYLOAD:
            if isinstance(action[1], dict):
                return BoundAction(name, command, (), action[1])
            return BoundAction(name, command, action[1], {})
        if len(action) == _NAME_ARGS_AND_KWARGS:
            positional, kwargs = action[1], action[2]
            if not isinstance(positional, (list, tuple)) or not isinstance(kwargs, dict):
                raise WebRunnerExecuteException(
                    f"{executor_data_error}: 3-element action requires [cmd, [positional], {{kwargs}}]"
                )
            return BoundAction(name, command, positional, kwargs)
        raise WebRunnerExecuteException(f"{executor_data_error} {action!s}")


class _ActionList:
    """Finds the actions as :meth:`Executor.action_list_of` does: an empty list runs nothing."""

    @staticmethod
    def extract(action_list: Any) -> list:
        """The list to run; raises for anything that is not a list or a dict holding one."""
        return Executor.action_list_of(action_list)


class _Reporter(PrintReporter):
    """Logs the list and each failure; prints every record's key and value (as :class:`PrintReporter`)."""

    def on_start(self, action_list: Any) -> None:
        web_runner_logger.info(f"execute_action, action_list: {action_list}")

    def on_failure(self, action: Any, error: Exception) -> None:
        web_runner_logger.error(f"execute_action, action: {action}, failed: {error!r}")


def _refuse_command(_name: str) -> WebRunnerAddCommandException:
    return WebRunnerAddCommandException(add_command_exception_tag)


class Executor(ActionExecutor):
    """
    執行 WebRunner 動作清單
    Runs WebRunner action lists: je_action_core's executor with WebRunner's action format, gates, retries,
    action spans and failure artifacts. ``event_dict`` is the live command table.
    """

    def __init__(self):
        super().__init__(
            ExecutorSettings(
                rules=_ActionList(),
                parser=_ActionParser(),
                reporter=_Reporter(),
                read_json=read_action_json,
                failure_record=self._failure_text,
                duplicate_keys=DuplicateKeys.NUMBER,
            ),
            CommandRegistry(policy=CommandPolicy.FUNCTIONS_ONLY, rejection=_refuse_command),
        )
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
        # 暫時拒絕的命令（見 restricted()）/ Commands refused for now; see restricted().
        self._denied_commands: frozenset[str] = frozenset()
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        self.event_dict = build_event_dict(self)

        # 只把允許清單裡的內建函式加入事件字典
        # Register only the allowlisted builtins.
        self.event_dict.update(safe_builtin_commands())

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

    def attempt(self, action: Any) -> Any:
        """
        執行單一動作（含重試與 span），失敗時拋出
        Run one action under the retry policy and the action span; what every action of a list passes.
        """
        return self._execute_with_retry(action)

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
        target = self._failure_artifact_path(action, ".png")
        if target is None:
            return None
        try:
            target.write_bytes(png)
            return str(target)
        except OSError as error:
            web_runner_logger.error(f"failure screenshot write failed: {error!r}")
            return None

    def _capture_failure_trace(self, action) -> str | None:
        """Save the running Playwright trace beside the failure screenshot. Returns path or None."""
        wrapper = _pw.playwright_wrapper_instance
        if not self.failure_screenshot_dir or not getattr(wrapper, "tracing_active", False):
            return None
        target = self._failure_artifact_path(action, ".trace.zip")
        if target is None:
            return None
        try:
            return wrapper.save_trace_chunk(str(target))
        except Exception as error:  # the action already failed; its trace is best effort
            web_runner_logger.error(f"failure trace save failed: {error!r}")
            return None

    def _failure_artifact_path(self, action, suffix: str) -> Path | None:
        """``<failure dir>/<timestamp>_<command><suffix>``, or None if it would leave the directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        raw_name = str(action[0] if isinstance(action, list) and action else "unknown")
        # Strip any path separators and limit to safe characters; otherwise an
        # action JSON could ship a command name like ``../../etc/passwd`` and
        # cause a path traversal write (SonarCloud S2083).
        safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in "-_")[:64] or "unknown"
        base_dir = Path(self.failure_screenshot_dir).resolve()
        target = (base_dir / f"{timestamp}_{safe_name}{suffix}").resolve()
        # Belt-and-braces: confirm the resolved path stays inside the
        # configured directory before writing.
        try:
            target.relative_to(base_dir)
        except ValueError:
            web_runner_logger.error(
                f"failure artifact path escapes configured dir: {target!r}"
            )
            return None
        return target

    def set_allow_arbitrary_script(self, enabled: bool) -> None:
        """
        切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令
        Toggle the gate for arbitrary-script commands. Disable when action
        JSON files are not fully trusted.
        """
        self.allow_arbitrary_script = bool(enabled)

    @staticmethod
    def set_raise_wrapper_errors(enabled: bool) -> None:
        """
        設定 Selenium wrapper 失敗時是否讓動作失敗
        ``True`` (the default): a failed Selenium wrapper call (``WR_to_url``,
        ``WR_element_assert`` …) fails its action, as the Playwright commands do. ``False``:
        the call returns and the action passes, the behaviour before the default changed.
        """
        set_raise_wrapper_errors(enabled)

    @staticmethod
    def set_allow_arbitrary_packages(enabled: bool) -> None:
        """
        允許或拒絕載入允許清單以外的套件（``WR_add_package_to_executor``）
        Allow (True) or refuse (False, the default) ``WR_add_package_to_executor`` for packages
        outside the allowlist. Python only, never an action command, so an action file cannot
        open its own gate.
        """
        package_manager.set_allow_arbitrary_packages(enabled)

    @staticmethod
    def allow_packages(*packages: str) -> None:
        """
        把套件（連同子模組）加入 ``WR_add_package_to_executor`` 的允許清單
        Add packages, and their submodules, to the allowlist of ``WR_add_package_to_executor``.
        """
        package_manager.allow_packages(*packages)

    @contextlib.contextmanager
    def restricted(self, denied_commands: Iterable[str]) -> Iterator[None]:
        """
        在區塊內拒絕指定命令（包含巢狀的動作清單）
        Refuse ``denied_commands`` for the duration of the ``with`` block, including in
        action lists run from inside it (``WR_execute_action``, ``WR_execute_files`` …),
        because every action passes :meth:`_execute_event`. Blocks nest; each adds to the
        commands already refused.
        """
        previous = self._denied_commands
        self._denied_commands = previous | frozenset(denied_commands)
        try:
            yield
        finally:
            self._denied_commands = previous

    def check_allowed(self, command: str, script_commands: Iterable[str] = ()) -> None:
        """
        檢查命令是否被拒絕或被任意腳本閘門擋下
        Raise :class:`WebRunnerExecuteException` when ``command`` is refused here
        (:meth:`restricted`) or ships a script while the arbitrary-script gate is closed.
        ``script_commands`` adds script commands of another command table (the async one).
        """
        if command in self._denied_commands:
            raise WebRunnerExecuteException(f"command {command!r} is not allowed here")
        if command in (_ARBITRARY_SCRIPT_COMMANDS | frozenset(script_commands)) and not self.allow_arbitrary_script:
            raise WebRunnerExecuteException(
                f"arbitrary-script command {command!r} is disabled; "
                "call WR_set_allow_arbitrary_script(true) to enable"
            )

    def _execute_event(self, action: list):
        """
        執行單一動作一次（不重試）
        Refuse a denied or gated command, then bind ``action`` and run it once (no retry). Raises what the
        refusal, the binding (see :class:`_ActionParser`) or the command raises.
        """
        self.check_allowed(action[0])
        return super()._execute_event(action)

    def execute_one(self, action: list) -> Any:
        """
        執行單一動作並回傳結果；失敗時拋出例外，不印出任何東西
        Run one action (``["WR_name"]``, ``["WR_name", {kwargs}]``, ``["WR_name", [args]]``
        or ``["WR_name", [args], {kwargs}]``) the way :meth:`execute_action` runs each step
        (refused commands, the arbitrary-script gate, the retry policy, the action span, the
        failure screenshot and trace) and return what the command returned. Prints nothing.

        :raises WebRunnerExecuteException: when the action is malformed or fails; the message
                 names any failure screenshot or trace, and the original error is ``__cause__``.
        """
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            raise WebRunnerExecuteException(
                f"{executor_data_error}: an action is a list that starts with a command name, got {action!r}")
        web_runner_logger.info(f"execute_one, action: {action}")
        try:
            return self._execute_with_retry(action)
        except Exception as error:  # every failure leaves as one exception type, with its cause
            web_runner_logger.error(f"execute_one, action: {action}, failed: {error!r}")
            raise WebRunnerExecuteException(self._failure_text(action, error)) from error

    @staticmethod
    def action_list_of(action_list: list | dict) -> list:
        """The action list itself, or a dict's ``webdriver_wrapper`` list; raises for anything else."""
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
        artifacts = []
        screenshot_path = self._capture_failure_screenshot(action)
        if screenshot_path:
            artifacts.append(f"failure screenshot: {screenshot_path}")
        trace_path = self._capture_failure_trace(action)
        if trace_path:
            artifacts.append(f"trace: {trace_path}")
        described = describe_error(error)
        return f"{described} ({'; '.join(artifacts)})" if artifacts else described

    def execute_files(self, execute_files_list: list) -> list:
        """
        從檔案載入並執行動作
        Run the action file at every path, in order, and return their records.
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        return super().execute_files(execute_files_list)


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
    executor.add_command_to_executor(command_dict)


def execute_action(action_list: list) -> dict:
    """
    全域方法：執行動作清單
    Global method: execute action list
    """
    return executor.execute_action(action_list)


def execute_one(action: list) -> Any:
    """
    全域方法：執行單一動作，失敗時拋出
    Global method: run one action and return its value; see :meth:`Executor.execute_one`.
    """
    return executor.execute_one(action)


def execute_files(execute_files_list: list) -> list:
    """
    全域方法：執行檔案中的動作
    Global method: execute actions from files
    """
    return executor.execute_files(execute_files_list)
