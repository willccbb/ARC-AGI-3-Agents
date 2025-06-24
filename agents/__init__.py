from typing import Type, cast

from dotenv import load_dotenv

from .agent import LLM, Agent, Playback, Random
from .swarm import Swarm
from .recorder import Recorder

load_dotenv()

AVAILABLE_AGENTS: dict[str, Type[Agent]] = {
    cls.__name__.lower(): cast(Type[Agent], cls)
    for cls in Agent.__subclasses__()
    if cls.__name__ != "Playback"
}

# add all the recording files as valid agent names
for rec in Recorder.list():
    AVAILABLE_AGENTS[rec] = Playback

__all__ = [
    "Swarm",
    "Random",
    "LLM",
    "Agent",
    "Recorder",
    "Playback",
    "AVAILABLE_AGENTS",
]
