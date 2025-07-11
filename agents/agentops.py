# agents/agentops.py
import functools
import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .agent import Agent

logger = logging.getLogger()


class _NoOpAgentOps:
    """A dummy class to use when agentops is not installed."""

    def init(self, *args: Any, **kwargs: Any) -> None:
        pass

    class _NoOpTrace:
        def __enter__(self) -> "_NoOpTrace":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

        def set_status(self, *args: Any, **kwargs: Any) -> None:
            pass

    def start_trace(self, *args: Any, **kwargs: Any) -> _NoOpTrace:
        return self._NoOpTrace()


try:
    import agentops

    logger.info("`agentops` library found, tracing enabled.")
except ImportError:
    logger.info("`agentops` not installed, tracing will be disabled.")
    agentops = _NoOpAgentOps()  # type: ignore


def initialize(api_key: Optional[str] = None) -> None:
    """Initializes the AgentOps SDK with an optional API key."""
    agentops.init(api_key=api_key, auto_start_session=False)


def trace_agent_session(func):
    """A decorator that wraps an agent's main execution loop to trace it."""

    @functools.wraps(func)
    def wrapper(agent_instance: "Agent", *args: Any, **kwargs: Any) -> Any:
        # 1. Tag Merging Strategy - User tags take precedence
        # Start with the most specific tags and work backwards.
        user_tags = getattr(agent_instance, "user_tags", []) or []
        final_tags = list(user_tags)
        final_tags.append(agent_instance.game_id)
        final_tags.append(agent_instance.name)

        # Deduplicate by keeping the last occurrence, which is the most specific one.
        final_tags.reverse()
        final_tags = list(dict.fromkeys(final_tags))
        final_tags.reverse()

        try:
            with agentops.start_trace(
                trace_name=agent_instance.name, tags=final_tags
            ) as trace:
                agent_instance.trace = trace
                result = func(agent_instance, *args, **kwargs)

                # 2. Set Final Status based on execution outcome
                # Note: AgentOps TraceContext may not have set_status method
                # The trace status is typically managed automatically by the context manager
                try:
                    if agent_instance.action_counter >= agent_instance.MAX_ACTIONS:
                        if hasattr(trace, "set_status"):
                            trace.set_status("Indeterminate")
                    else:
                        if hasattr(trace, "set_status"):
                            trace.set_status("Success")
                except AttributeError:
                    # AgentOps may handle status automatically
                    pass
                return result
        except Exception as e:
            if hasattr(agent_instance, "trace") and agent_instance.trace:
                try:
                    if hasattr(agent_instance.trace, "set_status"):
                        agent_instance.trace.set_status(f"Error: {e}")
                except AttributeError:
                    pass
            logger.error(
                f"Agent {agent_instance.name} failed with exception: {e}", exc_info=True
            )
            raise

    return wrapper
