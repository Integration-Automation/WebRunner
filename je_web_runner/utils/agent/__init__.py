"""Local browser agents: deterministic tasks or optional local Ollama planning."""
from je_web_runner.utils.agent.types import AgentAction, AgentError, AgentReport, SuccessCondition, TaskSpec
from je_web_runner.utils.agent.runner import AgentRunner, run_agent

__all__ = ["AgentAction", "AgentError", "AgentReport", "AgentRunner", "SuccessCondition", "TaskSpec", "run_agent"]
