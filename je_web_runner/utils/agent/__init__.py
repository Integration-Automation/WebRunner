"""Local browser agents: deterministic tasks or optional local Ollama planning."""
from je_web_runner.utils.agent.types import AgentAction, AgentError, AgentReport, SuccessCondition, TaskSpec
from je_web_runner.utils.agent.runner import AgentRunner, run_agent
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent.managed_browser import ManagedBrowserSession, ManagedBrowserError
from je_web_runner.utils.agent.managed_readonly import ManagedReadOnlySession

__all__ = ["AgentAction", "AgentError", "AgentReport", "AgentRunner", "SuccessCondition", "TaskSpec", "run_agent",
           "BrowserOriginPolicy", "ScopedBrowserProxy", "ManagedBrowserSession", "ManagedBrowserError",
           "ManagedReadOnlySession"]
