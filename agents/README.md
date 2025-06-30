# ARC-AGI-3 Agents

This directory contains the agent system for ARC-AGI-3, including the base agent classes, data structures, and various agent implementations.

## AI Play Testing

Agents interact with games via a JSON-based REST API by sending actions through the API and receiving game grids. Their goal is to `WIN` and avoid `GAME_OVER`. Each game grid is 2D with a maximum dimension of `(INT<0,63>, INT<0,63>)`. Each grid is made up of grid cells represented by `INT<0,15>` (each grid cell has 16 different possible states). A sequence of grids makes a frame. Every game uses the same universal set of actions (documented below). However, action semantics are game specific.

There are several default AI agents in the respository you can begin to experiment with! Here is a list of included agents:

* `random` - Selects actions randomly
* `llm` - Basic LLM agent using OpenAI models for decision making
* `reasoningllm` - LLM agent that uses o4-mini and captures reasoning metadata.
* `fastllm` - Similar to the LLM agent but skips observations for faster execution
* `guidedllm` - LLM agent with explicit human-provided rules (for a specific game) to increase success rate on that game

Note: LLM agents use OpenAI models, place your OpenAI API key in `.env`

You can run an agent like this, which opens a browser to view gameplay:

```bash
uv run main.py --agent=random --game=locksmith
```

The above command will play one specific game. You can also play all games like this:

```bash
uv run main.py --agent=random
```

## Agent Templates and Quickstart

For easy-to-use starting points and examples, check out the [Agent Templates](templates/README.md) which provide ready-to-use agent classes and customizable examples.

## Agent API Reference

### Creating a Custom Agent

To create a custom agent, inherit from the `Agent` base class and implement the required abstract methods.

Look at the [Agent Templates](templates/README.md) README for a quickstart and examples.

### Base Agent Class

The `Agent` class provides the following key features:

#### Properties
- `state: GameState` - Current game state (WIN, GAME_OVER, NOT_FINISHED)
- `score: int` - Current game score
- `action_counter: int` - Number of actions taken
- `frames: list[FrameData]` - All frames from the current session
- `fps: float` - Actions per second performance metric

#### Configuration
- `MAX_ACTIONS: int = 80` - Maximum actions before auto-termination
- `card_id: str` - Scorecard ID for tracking performance
- `game_id: str` - The specific game being played
- `guid: str` - Unique identifier for this game session

### Data Structures

#### FrameData
Represents a single frame of game data:
```python
class FrameData(BaseModel):
    game_id: str = ""
    frame: list[list[list[int]]] = [] # 3D array representing game grids
    state: GameState = GameState.NOT_PLAYED
    score: int = Field(0, ge=0, le=254)
    action_input: ActionInput = Field(default_factory=lambda: ActionInput())
    guid: Optional[str] = None
    full_reset: bool = False
```

#### GameAction
Enum representing all possible actions:
- `RESET` - Reset the game to initial state
- `ACTION1` through `ACTION5` - Simple actions (game-specific semantics)
- `ACTION6` - Complex action requiring x,y coordinates

Further explanation is in the [Game Actions](#game-actions) section.

```python
# Simple action
action = GameAction.ACTION1
action.set_data({"game_id": "your_game_id"})

# Complex action with coordinates
action = GameAction.ACTION6
action.set_data({"game_id": "your_game_id", "x": 5, "y": 10})
```

#### GameState
Enum representing game states:
- `NOT_PLAYED` - Game hasn't started
- `NOT_FINISHED` - Game is in progress
- `WIN` - Player has won
- `GAME_OVER` - Player has lost

### Error Handling/Limits

- Agents automatically stop after `MAX_ACTIONS` to prevent infinite loops (default is 100)
- Validation ensures all action data is properly formatted
- Scorecard system tracks both successes and failures (see `get_scorecard()` in `agent.py`)

## Recording and Playback

The ARC-AGI-3 agent system includes recording and playback functionality for analyzing agent behavior and debugging gameplay sessions.

### Automatic Recording

All agent gameplay is automatically recorded by default and stored in the `recordings/` directory with GUID-based filenames like:
```
locksmith-6cbb1acf0530.random.100.a1b2c3d4-e5f6-7890-abcd-ef1234567890.recording.jsonl
```

The filename format is: `{game_id}.{agent_type}.{max_actions}.{guid}.recording.jsonl`

You will be able to view these recordings in the Arc UI.

### Recording File Format

Recordings are stored in JSONL format with timestamped entries:

```json
{"timestamp": "2024-01-15T10:30:45.123456+00:00", "data": {"game_id": "locksmith", "frame": [...], "state": "NOT_FINISHED", "score": 5, "action_input": {"id": 0, "data": {"game_id": "locksmith"}, "reasoning": "..."}, "guid": "...", "full_reset": false}}
{"timestamp": "2024-01-15T10:30:46.234567+00:00", "data": {"game_id": "locksmith", "frame": [...], "state": "NOT_FINISHED", "score": 6, "action_input": {"id": 1, "data": {"game_id": "locksmith"}, "reasoning": "..."}, "guid": "...", "full_reset": false}}
```

### Playback Functionality

The system includes a Playback agent that can replay previously recorded sessions.

#### Running Playback

To replay a recorded session, use the recording filename as the agent name:

```bash
uv run main.py --agent="game.agent.100.guid.recording.jsonl" --game=game
```

Example:
```bash
uv run main.py --agent="locksmith-6cbb1acf0530.random.100.ee8571b9-0210-4ec4-8cfe-1a194f32e154.recording.jsonl" --game=locksmith
```

After running an agent, you can view the visual replay of the gameplay session on the ARC-AGI-3 website.

## Game Actions

All allowable actions:
* `RESET`
* `ACTION1`
* `ACTION2`
* `ACTION3`
* `ACTION4`
* `ACTION5`
* `ACTION6` `{x: INT<0,63>, y: INT<0,63>}`

Actions 1 through 5 are simple actions that represent a single input into the game. Action 6 is a complex action which requires you to also send an `x, y` game grid coordinate.

Games are allowed to assign semantics to both simple and complex actions however they see fit. For example, a game could assign the following semantics:
* `ACTION1`: move up
* `ACTION2`: move down
* `ACTION3`: move left
* `ACTION4`: move right
* `ACTION5`: use/interact with current cell
* `ACTION6`: select cell `x, y`

Discovering and interpreting semantics for each game is intentionally part of the challenge. The ARC-AGI-3 game state never advances without player input.

Every action response contains a `score` with range `INT<0,254>`. The score represents your level progression in the game. A score of 0 indicates you have yet to beat level 1, while a score of 5 would indicate you've passed level 5 and are on level 6 (if the game has it). Games are free to have as many levels as they wish, but they will always have at least one level.

Every action will result in at least one grid in the frame. However, some games may occasionally return multiples frame grids per action in order to show sequential intermediate game states.

For example, if a player pushes a object in the middle of the grid, a game may return sequential grids showing the object moving one grid cell at a time all the way to the edge of the grid.

Beating a level is indicated by an incrementing of the score by one _and_ two or more frames being returned in the response.