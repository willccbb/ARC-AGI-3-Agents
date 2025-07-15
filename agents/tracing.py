"""AgentOps integration module for tracing agent execution."""

import functools
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from .agent import Agent

# Module-level variables
logger = logging.getLogger()
AGENTOPS_LIBRARY_AVAILABLE = False
is_initialized = False
agentops_client: Optional[Any] = None


class NoOpAgentOps:
    """No-op implementation when AgentOps is not available."""

    def init(self, *args: Any, **kwargs: Any) -> None:
        """No-op initialization."""
        pass

    class NoOpTrace:
        """No-op trace context manager."""

        def __enter__(self) -> "NoOpAgentOps.NoOpTrace":
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

        def set_status(self, *args: Any, **kwargs: Any) -> None:
            """No-op status setting."""
            pass

    def start_trace(self, *args: Any, **kwargs: Any) -> NoOpTrace:
        """Create a no-op trace context."""
        return self.NoOpTrace()


# Try to import AgentOps library
try:
    import agentops as agentops_module

    AGENTOPS_LIBRARY_AVAILABLE = True
    agentops_client = agentops_module
    logger.info("AgentOps library found, available for initialization")
except ImportError:
    agentops_client = NoOpAgentOps()
    logger.info("AgentOps not installed, tracing will be disabled")


def initialize(
    api_key: Optional[str] = None, log_level: Optional[int] = logging.INFO
) -> bool:
    """Initialize the AgentOps SDK with an optional API key.

    Args:
        api_key: Optional AgentOps API key

    Returns:
        bool: True if successfully initialized, False otherwise
    """
    global is_initialized

    if not AGENTOPS_LIBRARY_AVAILABLE:
        logger.info("AgentOps not available - using no-op implementation")
        return False

    if not api_key:
        logger.warning("No AgentOps API key provided - using no-op implementation")
        return False

    if agentops_client is None:
        logger.error("AgentOps client not initialized")
        return False

    try:
        agentops_client.init(
            api_key=api_key,
            auto_start_session=False,
            log_level=log_level,
        )
        is_initialized = True
        logger.info("AgentOps successfully initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize AgentOps: {e}")
        return False


def is_available() -> bool:
    """Check if AgentOps is available and initialized."""
    return AGENTOPS_LIBRARY_AVAILABLE and is_initialized


def _set_trace_status(trace: Any, agent_instance: "Agent") -> None:
    """Set trace status based on agent execution outcome."""
    if not hasattr(trace, "set_status"):
        return

    try:
        if agent_instance.action_counter >= agent_instance.MAX_ACTIONS:
            trace.set_status("Indeterminate")
        else:
            trace.set_status("Success")
    except AttributeError:
        # AgentOps may handle status automatically
        pass


def _handle_trace_error(trace: Any, agent_instance: "Agent", error: Exception) -> None:
    """Handle trace error by setting error status."""
    if hasattr(trace, "set_status"):
        try:
            trace.set_status(f"Error: {error}")
        except AttributeError:
            pass


def trace_agent_session(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that wraps an agent's main execution loop to trace it."""

    @functools.wraps(func)
    def wrapper(agent_instance: "Agent", *args: Any, **kwargs: Any) -> Any:
        if not is_available():
            logger.debug("AgentOps not available - skipping tracing")
            return func(agent_instance, *args, **kwargs)

        tags = agent_instance.tags or []
        logger.debug(
            f"Starting AgentOps trace for {agent_instance.name} with tags: {tags}"
        )

        if agentops_client is None:
            logger.error("AgentOps client not available")
            return func(agent_instance, *args, **kwargs)

        trace = None
        try:
            with agentops_client.start_trace(
                trace_name=agent_instance.name, tags=tags
            ) as trace:
                agent_instance.trace = trace
                result = func(agent_instance, *args, **kwargs)
                _set_trace_status(trace, agent_instance)
                return result
        except Exception as e:
            if trace is not None:
                _handle_trace_error(trace, agent_instance, e)
            logger.error(
                f"Agent {agent_instance.name} failed with exception: {e}", exc_info=True
            )
            raise

    return wrapper
