"""AsyncExecutor with a fake browser pool: order, threads, gates, sessions, concurrency."""
import asyncio
import threading
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.async_executor import commands, executor as async_module
from je_web_runner.utils.async_executor.executor import AsyncExecutor
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor


class _FakeSession:
    def __init__(self, name):
        self.name = name
        self.closed = False
        self.calls = []

    async def close(self):
        self.closed = True


class _FakePool:
    def __init__(self):
        self.sessions = []

    async def open_session(self, **options):
        session = _FakeSession(f"user{len(self.sessions)}")
        session.options = options
        self.sessions.append(session)
        return session

    async def close(self):
        self.closed = True


async def _echo(session, value=None):
    session.calls.append(value)
    return f"{session.name}:{value}"


async def _boom(session):
    raise commands.AsyncCommandError("title is 'Home', expected it to contain 'Cart'")


class TestAsyncExecutor(unittest.TestCase):

    def setUp(self):
        self.sync = Executor()
        self.sync_threads = []
        self.sync.event_dict["WR_probe"] = self._probe
        self.runner = AsyncExecutor(sync=self.sync)
        self.runner.pool = _FakePool()
        patcher = patch.dict(async_module.ASYNC_COMMANDS, {"WR_apw_echo": _echo, "WR_apw_boom": _boom})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _probe(self):
        self.sync_threads.append(threading.get_ident())
        return "sync"

    def _run(self, coroutine):
        return asyncio.run(coroutine)

    def test_runs_in_order_with_sync_commands_in_a_worker_thread(self):
        record, failed = self._run(self.runner.run([
            ["WR_apw_echo", {"value": 1}], ["WR_probe"], ["WR_apw_echo", [2]], ["len", [[1, 2, 3]]]]))
        self.assertEqual(failed, [])
        self.assertEqual(list(record.values()), ["user0:1", "sync", "user0:2", 3])
        self.assertNotEqual(self.sync_threads, [threading.get_ident()])
        [session] = self.runner.pool.sessions
        self.assertEqual(session.calls, [1, 2])
        self.assertTrue(session.closed)

    def test_failures_are_recorded_and_the_list_goes_on(self):
        self.sync.event_dict["WR_sync_fail"] = MagicMock(side_effect=ValueError("bad value"))
        record, failed = self._run(self.runner.run([["WR_apw_boom"], ["WR_sync_fail"], ["WR_apw_echo", [3]]]))
        self.assertEqual(len(failed), 2)
        values = list(record.values())
        self.assertIn("expected it to contain 'Cart'", values[0])
        self.assertEqual(values[1], "ValueError('bad value')")
        self.assertEqual(values[2], "user0:3")

    def test_no_browser_session_for_sync_only_lists(self):
        self._run(self.runner.run([["WR_probe"]]))
        self.assertEqual(self.runner.pool.sessions, [])

    def test_gates_apply_to_async_commands(self):
        with self.sync.restricted({"WR_apw_echo"}):
            _record, failed = self._run(self.runner.run([["WR_apw_echo", [1]]]))
        self.assertEqual(len(failed), 1)
        self.sync.set_allow_arbitrary_script(False)
        record, failed = self._run(self.runner.run([["WR_apw_evaluate", {"script": "1"}]]))
        self.assertIn("arbitrary-script", record[failed[0]])
        self.assertEqual(self.runner.pool.sessions, [])

    def test_malformed_actions_and_lists(self):
        _record, failed = self._run(self.runner.run([[], ["WR_apw_echo", "not args"]]))
        self.assertEqual(len(failed), 2)
        with self.assertRaises(WebRunnerExecuteException):
            self._run(self.runner.run("not a list"))

    def test_run_many_keeps_order_isolates_sessions_and_limits_concurrency(self):
        active = {"now": 0, "most": 0}

        async def slow(session, value):
            active["now"] += 1
            active["most"] = max(active["most"], active["now"])
            await asyncio.sleep(0.05)
            active["now"] -= 1
            return f"{session.name}:{value}"
        with patch.dict(async_module.ASYNC_COMMANDS, {"WR_apw_slow": slow}):
            results = self._run(self.runner.run_many(
                [[["WR_apw_slow", [n]]] for n in range(5)], concurrency=2, context_options={"locale": "zh-TW"}))
        self.assertEqual([list(record.values())[0].split(":")[1] for record, _failed in results],
                         ["0", "1", "2", "3", "4"])
        self.assertEqual(active["most"], 2)
        self.assertEqual(len(self.runner.pool.sessions), 5)
        self.assertEqual(self.runner.pool.sessions[0].options, {"locale": "zh-TW"})
        with self.assertRaises(WebRunnerExecuteException):
            self._run(self.runner.run_many([], concurrency=0))


class TestSessionPages(unittest.TestCase):

    def test_no_page_and_switching(self):
        from je_web_runner.utils.async_executor.session import AsyncSession, AsyncSessionError
        session = AsyncSession(MagicMock())
        with self.assertRaises(AsyncSessionError):
            _ = session.page
        session.pages = ["first", "second"]
        self.assertEqual(session.switch_to(0), "first")
        with self.assertRaises(AsyncSessionError):
            session.switch_to(5)

    def test_unknown_browser(self):
        from je_web_runner.utils.async_executor.session import AsyncBrowserPool, AsyncSessionError
        with self.assertRaises(AsyncSessionError):
            AsyncBrowserPool("netscape")


class TestSyncTableKnowsAsyncCommands(unittest.TestCase):

    def test_validation_passes_and_running_synchronously_explains_where_it_runs(self):
        import json
        import tempfile
        from pathlib import Path

        from je_web_runner.utils.executor.action_executor import executor
        from je_web_runner.utils.json.json_validator import validate_action_file

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journey.json"
            path.write_text(json.dumps([["WR_apw_goto", {"url": "https://x.test/"}],
                                        ["WR_apw_click", {"selector": "#buy"}]]), encoding="utf-8")
            validate_action_file(str(path))
        record, failed = executor.collect_action_results([["WR_apw_click", {"selector": "#buy"}]])
        self.assertIn("runs only in the async executor", record[failed[0]])


if __name__ == "__main__":
    unittest.main()
