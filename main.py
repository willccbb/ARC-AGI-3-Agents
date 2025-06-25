# ruff: noqa: E402
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env-example")
load_dotenv(dotenv_path=".env", override=True)

import argparse
import logging
import os
import signal
import sys
import threading
from functools import partial
from types import FrameType
from typing import Optional

import requests

from agents import AVAILABLE_AGENTS, Swarm

logger = logging.getLogger()

SCHEME = os.environ.get("SCHEME", "http")
HOST = os.environ.get("HOST", "localhost")
PORT = os.environ.get("PORT", 8001)
ROOT_URL = f"{SCHEME}://{HOST}:{PORT}/"
HEADERS = {
    "X-API-Key": os.getenv("ARC_API_KEY", ""),
    "Accept": "application/json",
}


def run_agent(swarm: Swarm) -> None:
    swarm.main()
    os.kill(os.getpid(), signal.SIGINT)


def cleanup(
    swarm: Swarm,
    signum: Optional[int],
    frame: Optional[FrameType],
) -> None:
    if swarm.card_id:
        scorecard = swarm.close_scorecard(swarm.card_id)
        if scorecard:
            swarm.cleanup(scorecard)


def main() -> None:
    log_level = logging.INFO
    if os.environ.get("DEBUG", "False") == "True":
        log_level = logging.DEBUG

    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler("logs.log", mode="w")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

    # logging.getLogger("requests").setLevel(logging.CRITICAL)
    # logging.getLogger("werkzeug").setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(description="ARC-AGI-3-Agents")
    parser.add_argument(
        "-a",
        "--agent",
        choices=AVAILABLE_AGENTS.keys(),
        help="Choose which agent to run.",
    )
    parser.add_argument(
        "-g",
        "--game",
        help="Choose a specific game_id for the agent to play. If none specified, an agent swarm will play all available games.",
    )

    args = parser.parse_args()

    if not args.agent:
        logger.error("An Agent must be specified")
        return

    print(f"{ROOT_URL}/api/games")

    # Get the list of games from the API
    with requests.Session() as session:
        session.headers.update(HEADERS)
        r = session.get(f"{ROOT_URL}/api/games")
        
    games = [g["game_id"] for g in r.json()]
    if args.game:
        filters = args.game.split(",")
        games = [
            gid for gid in games if any(gid.startswith(prefix) for prefix in filters)
        ]

    logger.info(f"Game list returned from API: {games}")

    swarm = Swarm(
        args.agent,
        ROOT_URL,
        games,
    )
    agent_thread = threading.Thread(target=partial(run_agent, swarm))
    agent_thread.daemon = True  # die when the main thread dies
    agent_thread.start()

    signal.signal(signal.SIGINT, partial(cleanup, swarm))  # handler for Ctrl+C

    agent_thread.join()


if __name__ == "__main__":
    os.environ["TESTING"] = "False"
    main()
