import json
import logging
import os
import random
import textwrap
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import requests
from pydantic import ValidationError
from requests import Response

from .recorder import Recorder
from .structs import FrameData, GameAction, GameState, Scorecard

logger = logging.getLogger()


class Agent(ABC):
    """Interface for an agent that plays one ARC-AGI-3 game."""

    MAX_ACTIONS: int = 100  # to avoid looping forever if agent doesnt exit
    ROOT_URL: str

    action_counter: int = 0

    timer: float = 0
    agent_name: str
    card_id: str
    game_id: str
    guid: str
    frames: list[FrameData]

    recorder: Recorder
    headers: dict[str, str]

    def __init__(
        self,
        card_id: str,
        game_id: str,
        agent_name: str,
        ROOT_URL: str,
        record: bool,
    ) -> None:
        self.ROOT_URL = ROOT_URL
        self.card_id = card_id
        self.game_id = game_id
        self.guid = ""
        self.agent_name = agent_name
        self.frames = [FrameData(score=0)]
        self._cleanup = True
        if record:
            self.start_recording()
        self.headers = {
            "X-API-Key": os.getenv("ARC_API_KEY", ""),
            "Accept": "application/json",
        }

    def main(self) -> None:
        """The main agent loop. Play the game_id until finished, then exits."""
        self.timer = time.time()
        while (
            not self.is_done(self.frames, self.frames[-1])
            and self.action_counter <= self.MAX_ACTIONS
        ):
            action = self.choose_action(self.frames, self.frames[-1])
            if frame := self.take_action(action):
                self.append_frame(frame)
                logger.info(
                    f"{self.game_id} - {action.name}: count {self.action_counter}, score {frame.score}, avg fps {self.fps})"
                )
            self.action_counter += 1
        self.cleanup()

    @property
    def state(self) -> GameState:
        return self.frames[-1].state

    @property
    def score(self) -> int:
        return self.frames[-1].score

    @property
    def seconds(self) -> float:
        return (time.time() - self.timer) * 100 // 1 / 100

    @property
    def fps(self) -> float:
        if self.action_counter == 0:
            return 0.0
        elapsed_time = max(self.seconds, 0.1)
        return round(self.action_counter / elapsed_time, 2)

    @property
    def is_playback(self) -> bool:
        return type(self) is Playback

    @property
    def name(self) -> str:
        n = self.__class__.__name__.lower()
        return f"{self.game_id}.{n}"

    def start_recording(self) -> None:
        filename = self.agent_name if self.is_playback else None
        self.recorder = Recorder(prefix=self.name, filename=filename)
        logger.info(
            f"created new recording for {self.name} into {self.recorder.filename}"
        )

    def append_frame(self, frame: FrameData) -> None:
        self.frames.append(frame)
        if frame.guid:
            self.guid = frame.guid
        if hasattr(self, "recorder") and not self.is_playback:
            self.recorder.record(json.loads(frame.model_dump_json()))

    def do_action_request(self, action: GameAction) -> Response:
        data = action.action_data.model_dump()
        if action == GameAction.RESET:
            data["card_id"] = self.card_id
        if self.guid:
            data["guid"] = self.guid
        if action.reasoning:
            data["reasoning"] = action.reasoning

        json_str = json.dumps(data)
        r = requests.post(
            f"{self.ROOT_URL}/api/cmd/{action.name}",
            json=json.loads(json_str),
            headers=self.headers,
        )
        if "error" in r.json():
            logger.warning(f"Exception during action request: {r.json()}")
        return r

    def take_action(self, action: GameAction) -> Optional[FrameData]:
        """Submits the specific action and gets the next frame."""
        frame_data = self.do_action_request(action).json()
        try:
            frame = FrameData.model_validate(frame_data)
        except ValidationError as e:
            logger.warning(f"Incoming frame data did not validate: {e}")
            return None
        return frame

    def get_scorecard(self) -> dict[str, Any]:
        # TODO: make scorecard a pydantic type
        r = requests.get(
            f"{self.ROOT_URL}/api/scorecard/{self.card_id}/{self.game_id}",
            timeout=1,
            headers=self.headers,
        )
        if "error" in r.json():
            logger.warning(f"Exception during scorecard request: {r.json()}")
        data: dict[str, Any] = r.json()
        return data

    def cleanup(self, scorecard: Optional[Scorecard] = None) -> None:
        """Called after main loop is finished."""
        if self._cleanup:
            self._cleanup = False  # only cleanup once per agent
            if hasattr(self, "recorder") and not self.is_playback:
                if scorecard:
                    self.recorder.record(scorecard.get(self.game_id))
                else:
                    self.recorder.record(self.get_scorecard())
                logger.info(
                    f"recording for {self.name} is available in {self.recorder.filename}"
                )
            if self.action_counter >= self.MAX_ACTIONS:
                logger.info(
                    f"Exiting: agent reached MAX_ACTIONS of {self.MAX_ACTIONS}, took {self.seconds} seconds ({self.fps} average fps)"
                )
            else:
                logger.info(
                    f"Finishing: agent took {self.action_counter} actions, took {self.seconds} seconds ({self.fps} average fps)"
                )

    @abstractmethod
    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Decide if the agent is done playing or not."""
        raise NotImplementedError

    @abstractmethod
    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Choose which action the Agent should take, fill in any arguments, and return it."""
        raise NotImplementedError


class Playback(Agent):
    """An agent that plays back from a recorded session from another agent."""

    MAX_ACTIONS = 1000000
    PLAYBACK_FPS = 5

    recorded_actions: list[dict[str, Any]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recorder = Recorder(
            prefix=Recorder.get_prefix(self.agent_name),
            guid=Recorder.get_guid(self.agent_name),
        )
        self.recorded_actions = self.filter_actions()

    def filter_actions(self) -> list[dict[str, Any]]:
        return [
            a for a in self.recorder.get() if "data" in a and "game_id" in a["data"]
        ]

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return bool(self.action_counter >= len(self.recorded_actions))

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        rec_frame = self.recorded_actions[self.action_counter]["data"]
        frame = FrameData(**rec_frame)
        action = frame.action_input.id
        data = frame.action_input.data
        data["game_id"] = self.game_id
        action.set_data(data)
        time.sleep(1.0 / self.PLAYBACK_FPS)
        return action

    # overwrite append_frame to not double record
    def append_frame(self, frame: FrameData) -> None:
        self.frames.append(frame)
        if frame.guid:
            self.guid = frame.guid


class Random(Agent):
    """An agent that always selects actions at random."""

    MAX_ACTIONS = 100

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Decide if the agent is done playing or not."""
        return any(
            [
                latest_frame.state is GameState.WIN,
                # uncomment to only let the agent play one time
                # latest_frame.state is GameState.GAME_OVER,
            ]
        )

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Choose which action the Agent should take, fill in any arguments, and return it."""
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            # if game is not started (at init or after GAME_OVER) we need to reset
            # add a small delay before resetting after GAME_OVER to avoid timeout
            action = GameAction.RESET
        else:
            # else choose a random action that isnt reset
            action = random.choice([a for a in GameAction if a is not GameAction.RESET])
        if action.is_simple():
            action.set_data({"game_id": self.game_id})
            action.reasoning = f"RNG told me to pick {action.value}"
        elif action.is_complex():
            action.set_data(
                {
                    "game_id": self.game_id,
                    "x": random.randint(0, 63),
                    "y": random.randint(0, 63),
                }
            )
            action.reasoning = {
                "desired_action": f"{action.value}",
                "my_reason": "RNG said so!",
            }
        return action


class LLM(Agent):
    """An agent that uses a base LLM model to play games."""

    MAX_ACTIONS: int = 1000
    DO_OBSERVATION: bool = True
    REASONING_EFFORT: Optional[str] = None
    MODEL_REQUIRES_TOOLS: bool = False

    MESSAGE_LIMIT: int = 10
    MODEL: str = "gpt-4o-mini"
    messages: list[dict[str, Any]]
    token_counter: int

    _latest_tool_call_id: str = "call_12345"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.messages = []
        self.token_counter = 0

    @property
    def name(self) -> str:
        obs = "with-observe" if self.DO_OBSERVATION else "no-observe"
        name = f"{super().name}.{self.MODEL}.{obs}"
        if self.REASONING_EFFORT:
            name += f".{self.REASONING_EFFORT}"
        return name

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Decide if the agent is done playing or not."""
        return any(
            [
                latest_frame.state is GameState.WIN,
                # uncomment below to only let the agent play one time
                # latest_frame.state is GameState.GAME_OVER,
            ]
        )

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Choose which action the Agent should take, fill in any arguments, and return it."""
        import openai
        from openai import OpenAI as OpenAIClient

        logging.getLogger("openai").setLevel(logging.CRITICAL)
        logging.getLogger("httpx").setLevel(logging.CRITICAL)

        client = OpenAIClient(api_key=os.environ.get("OPENAI_SECRET_KEY", ""))

        functions = self.build_functions()
        tools = self.build_tools()

        # if latest_frame.state in [GameState.NOT_PLAYED]:
        if len(self.messages) == 0:
            # have to manually trigger the first reset to kick off agent
            user_prompt = self.build_user_prompt(latest_frame)
            message0 = {"role": "user", "content": user_prompt}
            self.push_message(message0)
            if self.MODEL_REQUIRES_TOOLS:
                message1 = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": self._latest_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": GameAction.RESET.name,
                                "arguments": json.dumps({}),
                            },
                        }
                    ],
                }
            else:
                message1 = {
                    "role": "assistant",
                    "function_call": {"name": "RESET", "arguments": json.dumps({})},  # type: ignore
                }
            self.push_message(message1)
            action = GameAction.RESET
            action.set_data({"game_id": self.game_id})
            return action

        # let the agent comment observations before choosing action
        # on the first turn, this will be in response to RESET action
        function_name = latest_frame.action_input.id.name
        function_response = self.build_func_resp_prompt(latest_frame)
        if self.MODEL_REQUIRES_TOOLS:
            message2 = {
                "role": "tool",
                "tool_call_id": self._latest_tool_call_id,
                "content": str(function_response),
            }
        else:
            message2 = {
                "role": "function",
                "name": function_name,
                "content": str(function_response),
            }
        self.push_message(message2)

        if self.DO_OBSERVATION:
            logger.info("Sending to Assistant for observation...")
            try:
                response = client.chat.completions.create(
                    model=self.MODEL,
                    messages=self.messages,
                    reasoning_effort=self.REASONING_EFFORT,
                )
            except openai.BadRequestError as e:
                logger.info(f"Message dump: {self.messages}")
                raise e
            self.track_tokens(
                response.usage.total_tokens, response.choices[0].message.content
            )
            message3 = {
                "role": "assistant",
                "content": response.choices[0].message.content,
            }
            logger.info(f"Assistant: {response.choices[0].message.content}")
            self.push_message(message3)

        # now ask for the next action
        user_prompt = self.build_user_prompt(latest_frame)
        message4 = {"role": "user", "content": user_prompt}
        self.push_message(message4)

        name = GameAction.ACTION5.name  # default action if LLM doesnt call one
        arguments = None
        message5 = None

        if self.MODEL_REQUIRES_TOOLS:
            logger.info("Sending to Assistant for action...")
            try:
                response = client.chat.completions.create(
                    model=self.MODEL,
                    messages=self.messages,
                    tools=tools,
                    tool_choice="required",
                    reasoning_effort=self.REASONING_EFFORT,
                )
            except openai.BadRequestError as e:
                logger.info(f"Message dump: {self.messages}")
                raise e
            self.track_tokens(response.usage.total_tokens)
            message5 = response.choices[0].message
            logger.debug(f"... got response {message5}")
            tool_call = message5.tool_calls[0]
            self._latest_tool_call_id = tool_call.id
            logger.debug(
                f"Assistant: {tool_call.function.name} ({tool_call.id}) {tool_call.function.arguments}"
            )
            name = tool_call.function.name
            arguments = tool_call.function.arguments

            # sometimes the model will call multiple tools which isnt allowed
            extra_tools = message5.tool_calls[1:]
            for tc in extra_tools:
                logger.info(
                    "Error: assistant called more than one action, only using the first."
                )
                message_extra = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "Error: assistant can only call one action (tool) at a time. default to only the first chosen action.",
                }
                self.push_message(message_extra)
        else:
            logger.info("Sending to Assistant for action...")
            try:
                response = client.chat.completions.create(
                    model=self.MODEL,
                    messages=self.messages,
                    functions=functions,
                    function_call="auto",
                    reasoning_effort=self.REASONING_EFFORT,
                )
            except openai.BadRequestError as e:
                logger.info(f"Message dump: {self.messages}")
                raise e
            self.track_tokens(response.usage.total_tokens)
            message5 = response.choices[0].message
            function_call = message5.function_call
            logger.debug(f"Assistant: {function_call.name} {function_call.arguments}")
            name = function_call.name
            arguments = function_call.arguments

        if message5:
            self.push_message(message5)
        action_id = name
        if arguments:
            try:
                data = json.loads(arguments) or {}
            except Exception as e:
                data = {}
                logger.warning(f"JSON parsing error on LLM function response: {e}")
        else:
            data = {}

        action = GameAction.from_name(action_id)
        data["game_id"] = self.game_id
        action.set_data(data)
        return action

    def track_tokens(self, tokens: int, message: str = "") -> None:
        self.token_counter += tokens
        if hasattr(self, "recorder") and not self.is_playback:
            self.recorder.record(
                {
                    "tokens": tokens,
                    "total_tokens": self.token_counter,
                    "assistant": message,
                }
            )
        logger.info(f"Received {tokens} tokens, new total {self.token_counter}")
        # handle tool to debug messages:
        # with open("messages.json", "w") as f:
        #     json.dump(
        #         [
        #             msg if isinstance(msg, dict) else msg.model_dump()
        #             for msg in self.messages
        #         ],
        #         f,
        #         indent=2,
        #     )

    def push_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """Push a message onto stack, store up to MESSAGE_LIMIT with FIFO."""
        self.messages.append(message)
        if len(self.messages) > self.MESSAGE_LIMIT:
            self.messages = self.messages[-self.MESSAGE_LIMIT :]
        if self.MODEL_REQUIRES_TOOLS:
            # cant clip the message list between tool
            # and tool_call else llm will error
            while (
                self.messages[0].get("role")
                if isinstance(self.messages[0], dict)
                else getattr(self.messages[0], "role", None)
            ) == "tool":
                self.messages.pop(0)
        return self.messages

    def build_functions(self) -> list[dict[str, Any]]:
        """Build JSON function description of game actions for LLM."""
        empty_params: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        functions: list[dict[str, Any]] = [
            {
                "name": GameAction.RESET.name,
                "description": "Start or restart a game. Must be called first when NOT_PLAYED or after GAME_OVER to play again.",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION1.name,
                "description": "Send this simple input action (1, A, Left).",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION2.name,
                "description": "Send this simple input action (2, D, Right).",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION3.name,
                "description": "Send this simple input action (3, W, Up).",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION4.name,
                "description": "Send this simple input action (4, S, Down).",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION5.name,
                "description": "Send this simple input action (5, Enter, Spacebar, Delete).",
                "parameters": empty_params,
            },
            {
                "name": GameAction.ACTION6.name,
                "description": "Send this complex input action (6, Click, Point).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "string",
                            "description": "Coordinate X which must be Int<0,63>",
                        },
                        "y": {
                            "type": "string",
                            "description": "Coordinate Y which must be Int<0,63>",
                        },
                    },
                    "required": ["x", "y"],
                    "additionalProperties": False,
                },
            },
        ]
        return functions

    def build_tools(self) -> list[dict[str, Any]]:
        """Support models that expect tool_call format."""
        functions = self.build_functions()
        tools: list[dict[str, Any]] = []
        for f in functions:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": f["name"],
                        "description": f["description"],
                        "parameters": f.get("parameters", {}),
                        "strict": True,
                    },
                }
            )
        return tools

    def build_func_resp_prompt(self, latest_frame: FrameData) -> str:
        return textwrap.dedent(
            """
# State:
{state}

# Score:
{score}

# Frame:
{latest_frame}

# TURN:
Reply with a few sentences of plain-text strategy observation about the frame to inform your next action.
        """.format(
                latest_frame=self.pretty_print_3d(latest_frame.frame),
                score=latest_frame.score,
                state=latest_frame.state.name,
            )
        )

    def build_user_prompt(self, latest_frame: FrameData) -> str:
        return textwrap.dedent(
            """
# CONTEXT:
You are an agent playing a dynamic game. Your objective is to
WIN and avoid GAME_OVER while minimizing actions.

One action produces one Frame. One Frame is made of one or more sequential
Grids. Each Grid is a matrix size INT<0,63> by INT<0,63> filled with
INT<0,15> values.

# TURN:
Call exactly one action.
        """.format()
        )

    def pretty_print_3d(self, array_3d: list[list[list[Any]]]) -> str:
        lines = []
        for i, block in enumerate(array_3d):
            lines.append(f"Grid {i}:")
            for row in block:
                lines.append(f"  {row}")
            lines.append("")
        return "\n".join(lines)

    def cleanup(self, *args: Any, **kwargs: Any) -> None:
        if self._cleanup:
            if hasattr(self, "recorder") and not self.is_playback:
                meta = {
                    "llm_user_prompt": self.build_user_prompt(self.frames[-1]),
                    "llm_tools": self.build_tools()
                    if self.MODEL_REQUIRES_TOOLS
                    else self.build_functions(),
                    "llm_tool_resp_prompt": self.build_func_resp_prompt(
                        self.frames[-1]
                    ),
                }
                self.recorder.record(meta)
        super().cleanup(*args, **kwargs)


class ReasoningLLM(LLM, Agent):
    """For LLMs with reasoning modes."""

    MAX_ACTIONS = 50
    DO_OBSERVATION = True
    MODEL_REQUIRES_TOOLS = True
    REASONING_EFFORT = "high"
    MODEL = "o3"


class FastLLM(LLM, Agent):
    """Similar to LLM, but skips observations."""

    MAX_ACTIONS = 100
    DO_OBSERVATION = False
    MODEL = "gpt-4o-mini"

    def build_user_prompt(self, latest_frame: FrameData) -> str:
        return textwrap.dedent(
            """
# CONTEXT:
You are an agent playing a dynamic game. Your objective is to
WIN and avoid GAME_OVER while minimizing actions.

One action produces one Frame. One Frame is made of one or more sequential
Grids. Each Grid is a matrix size INT<0,63> by INT<0,63> filled with
INT<0,15> values.

# TURN:
Call exactly one action.
        """.format()
        )


class GuidedLLM(LLM, Agent):
    """Similar to LLM, with explicit human-provided rules in the user prompt to increase success rate."""

    MAX_ACTIONS = 200
    DO_OBSERVATION = True
    MODEL = "o3"
    MODEL_REQUIRES_TOOLS = True
    MESSAGE_LIMIT = 10
    REASONING_EFFORT = "high"

    def build_user_prompt(self, latest_frame: FrameData) -> str:
        return textwrap.dedent(
            """
# CONTEXT:
You are an agent playing a dynamic game. Your objective is to
WIN and avoid GAME_OVER while minimizing actions.

One action produces one Frame. One Frame is made of one or more sequential
Grids. Each Grid is a matrix size INT<0,63> by INT<0,63> filled with
INT<0,15> values.

You are playing a game called LockSmith. Rules and strategy:
* RESET: start over, ACTION1: move left, ACTION2: move right, ACTION3: move up, ACTION4: move down (ACTION5 and ACTION6 do nothing in this game)
* you may may one action per turn
* your goal is find and collect a matching key then touch the exit door
* 6 levels total, score shows which level, complete all levels to win (grid row 62)
* start each level with limited energy. you GAME_OVER if you run out (grid row 61)
* the player is a 4x4 square: [[X,X,X,X],[0,0,0,X],[4,4,4,X],[4,4,4,X]] where X is transparent to the background
* the grid represents a birds-eye view of the level
* walls are made of INT<10>, you cannot move through a wall
* walkable floor area is INT<8>
* you can refill energy by touching energy pills (a 2x2 of INT<6>)
* current key is shown in bottom-left of entire grid
* the exit door is a 4x4 square with INT<11> border
* to find a new key shape, touch the key rotator, a 4x4 square denoted by INT<9> and INT<4> in the top-left corner of the square
* to find a new key color, touch the color rotator, a 4x4 square denoted by INT<9> and INT<2> and in the bottom-left corner of the square
* to rotate more than once, move 1 space away from the rotator and back on
* continue rotating the shape and color of the key until the key matches the one inside the exit door (scaled down 2X)
* if the grid does not change after an action, you probably tried to move into a wall

An example of a good strategy observation:
The player 4x4 made of INT<4> and INT<0> is standing below a wall of INT<10>, so I cannot move up anymore and should
move left towards the rotator with INT<11>.

# TURN:
Call exactly one action.
        """.format()
        )
