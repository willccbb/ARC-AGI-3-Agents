# ARC-AGI-3-Agents

ARC-AGI-3-Agents is a set of AI Agents designed to run against ARC-AGI-3, which is a set of novel, fun, ARC-like games which require only Core Knowledge to win. The games follow a data format similar to ARC-AGI-1 and ARC-AGI-2. However, instead of static input/output pairs with fixed answers, games are now dynamic.

## Changelog
TODO:
---

## Getting Started

1. First install [uv](https://docs.astral.sh/uv/getting-started/installation/) if not aready installed.

2. Then clone the repo and enter the directory.

```bash
git clone https://github.com/arcprize/ARC-AGI-3-Agents.git
```

3. Input your API key from the [ARC-AGI-3 Website](https://sandbox.internal.arc-prize.com/)

```bash
echo "ARC_API_KEY=your_api_key" > .env
```

4. Run the random against against all games

```bash
uv run main.py --agent=random
```

## AI play testing

AI interacts with games via JSON-based REST API by sending actions and receiving game grids to `WIN` (and avoid `GAME_OVER`). Each game grid is 2D with a maximum dimension of `INT<0,63>, INT<0,63>`. Each grid is made up of grid cells represented by `INT<0,15>`. A sequence of grids makes a frame. Every game uses the same universal set of actions (documented below). However, action semantics are game specific.

There are several AI agents included in the respository you can begin to experiment with (or add your own)! The list of included agents:

* `random`
* `llm`
* `fastllm`
* `guidedllm`
* `rlagent`

Note: LLM uses OpenAI models, place your OpenAI API key in `.env`

Run one like this, which opens a browser to view gameplay:

```bash
uv run main.py --agent=random
```

By default, this will create a swarm of agents to play all `GAMES` available to your key. You can just play one specific game like this:

```bash
uv run main.py --agent=random --game=locksmith
```

### Recording and playback

All Games are automatically recorded and stored in `recordings/` with GUID-based filenames.

## API Reference

### Get list of all games

Returns a list of all available `game_id`'s for the benchmark.

```bash
curl https://sandbox.internal.arc-prize.com/api/games \
    -H "X-API-Key: your_api_key_here"
```

```
RESPONSE:
[
    {
        "game_id":"locksmith-1d57d6daeb05",
        "title":"Locksmith"
    },
    {
        "game_id":"shiftex-91fcad9dbd17",
        "title":"Shiftex"
    }
    ...
]
```

### Open or Close a Scorecard

In order for scoring to be tracked you must open a scordcard. When openning a score card you can provide an optional `source_url` and `tags`.

**Note:** The built it `Swarm` class in `agents/agent.py` handles openning, closing, and displaying a scorecard for you.

```bash
curl https://sandbox.internal.arc-prize.com/api/scorecard/open \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key_here" \
    -d '{"source_url": "<link_to_source_or_noteboot>", tags: ["agent", "LLM-o4-mini"]}'
```

```
RESPONSE:
{
    "card_id": ":card_id"
}
```

Once your agent is finished you can close the scorecard.

```bash
curl https://sandbox.internal.arc-prize.com/api/scorecard/close \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key_here" \
    -d '{"card_id": ":card_id"}'
```
```
RESPONSE:
{
    "won": INT,
    "played": INT,
    "total_actions": INT,
    "score": INT,
    "source_url": ":source_url"
    "tags": [":tag1", "tag2"]
    "cards": {
        ...
        "locksmith": {
            "game_id": :game_id,
            "total_plays": INT,
            "total_actions": INT,
            "scores": list[INT],
            "states": list[Enum<NOT_FINISHED, WIN, GAME_OVER>]
            "actions": list[INT]
        },
        ...
    }
}
```

While your agent is running you can get scorecard information on a given `card_id` and (optional) `game_id`

```bash
curl https://sandbox.internal.arc-prize.com/api/scorecard/:card_id -H "X-API-Key: your_api_key_here"
curl https://sandbox.internal.arc-prize.com/api/scorecard/:card_id/:game_id -H "X-API-Key: your_api_key_here"
```

```
RESPONSE:
{
    "won": INT,
    "played": INT,
    "total_actions": INT,
    "score": INT,
    "source_url": ":source_url"
    "tags": [":tag1", "tag2"]
    "cards": {
        ...
        "locksmith": {
            "game_id": :game_id,
            "total_plays": INT,
            "total_actions": INT,
            "scores": list[INT],
            "states": list[Enum<NOT_FINISHED, WIN, GAME_OVER>]
            "actions": list[INT]
        },
        ...
    }
}
```

ARC-AGI-3 reports benchmarks scores along two axes: accuracy and efficiency. Accuracy can be assessed by looking at the count of games `won` while efficiency can assesed through the `total_actions` count. These top level properties sum across all game cards and plays.

It can be useful to have a more granular understanding of game progression, which you can get within game cards and via the top level `score`; which is the sum of the highest score in each individual game. A game can be played more than once thus individual play sessions are enumerated within lists `scores`, `states`, and `actions`. The index position in the list correlated with the play session.

Explanation of `states`:
* `NOT_FINISHED`: the game was started and is in progress but player never reached `WIN` or `GAME_OVER`
* `WIN`: the player reached the winning condition for the game
* `GAME_OVER`: the player triggered the losing condition for the game

Game `scores` are reported on cards. Scoring is non-monotonic and semantic per game (thus no absolute meaning). For example, in some games `score` may indicate which level the player is on. In others, it may be a count of items collected, etc. Universally, increasing `score` means the player is getting closer to winning.

Scorecards are tracked for the duration of the `main.py` process and many can be open and closed during the running `main.py`.

### Start (or reset) a game, receive the first game frame

You must always start by first issuing a `RESET` action to a `game_id` before you send other actions.

Issuing `RESET` again will return the specified `game_id` back to the beginning of the game.

Resetting will clear the game's latest play session (state, score, and action count). Note session detals are tracked across plays on the final [scorecard](#get-scorecard).

Each `game_id` can have many instances at a time so long as their `guid` is unique, you can run as many unique `game_id` + `guid` combinations as supported by the launch constraints.

Game state will be set to `GAME_OVER` or `WIN` to represent if the player has won or lost a specific `game_id` + `guid` in response to the latest action input. To try a game again, you must next issue a `RESET` action to the `game_id`.

Note: providing a `guid` for RESET is optional, but providing it will reset the game on the same driver as the previous session.  The `card_id` is also optional, but scoring is not tracked when `card_id` is not provided.

```bash
curl https://sandbox.internal.arc-prize.com/api/cmd/RESET \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key_here" \
    -d '{"game_id": ":game_id", "card_id", ":card_id", "guid": ":guid"}'
```

```
RESPONSE:
{
    "game_id": :game_id,
    "guid": :guid,
    "frame": [
        [[INT<0,15>, ...], ...],  // 2D grid, representing the beginning of the game
    ],
    "state": Enum<NOT_FINISHED, WIN, GAME_OVER>,
    "score": 0,
    "action_input": {
        "id": 0
        "data": {
            "x": 0,
            "y": 0
        }
    },
}
```

### Send simple action to a game, receive frame

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
* `ACTION1`: move left
* `ACTION2`: move right
* `ACTION3`: move up
* `ACTION4`: move down
* `ACTION5`: use
* `ACTION6`: select cell `x, y`

Discovering and interpretting semantics is intentionally part of the challenge.

Every action will result in at least one grid in the frame. However, some games may occasionally return multiples frame grids per action in order to show sequential intermediate game states.

For example, if a player pushes a object in the middle of the grid, a game may return sequential grids showing the object moving one grid cell at a time all the way to the edge of the grid.

**Important:** Unlike most modern video games, ARC-AGI-3 game state _never_ advances without player input! ARC-AGI-3 is an intelligence test that measures efficiency by action count, not response time.

Every action response contains a `score` with range `INT<0,254>`. Like action, score is sematic. Each game is free to interpret score as it sees fit. Some games do not use a score at all (and will always be `0`). Other games may only use a partial range. There is no universal score to indicate a game was been won. Therefore it is most useful as a relative indicator. Achieving a high score itself is explicitly _not_ a goal in ARC-AGI-3.

**Important:** Beating a level is indicated by an incrementing of the score by one _and_ a two or more frames being returned in the response.  This is how the human UI on the frontend knows to display the "Firework" animation.

```bash
curl https://sandbox.internal.arc-prize.com/api/cmd/ACTION1 \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key_here" \
    -d '{"game_id": ":game_id", "guid": ":guid"}'

```

```
RESPONSE:
{
    "game_id": :game_id,
    "guid": :guid,
    "frame": [
        [[INT<0,15>, ...], ...],  // 2D grid, representing the game immediately after action
        [[INT<0,15>, ...], ...],  // some games may advance multiple steps per action
        ...                       // but games never advance without action
    ],
    "state": Enum<NOT_FINISHED, WIN, GAME_OVER>,
    "score": INT<0,254>,
    "action_input": {
        "id": 1
        "data": {
            "x": 0,
            "y": 0
        }
    },
}
```

### Send complex action to a game, receive frame

```bash
curl https://sandbox.internal.arc-prize.com/api/cmd/ACTION6 \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-Key: your_api_key_here" \
    -d '{"game_id": ":game_id", "guid": ":guid", "x": INT<0,63>, "y": INT<0,63>}'
```

```
RESPONSE:
{
    "game_id": :game_id,
    "guid": :guid,
    "frame": [
        [[INT<0,15>, ...], ...],  // 2D grid
        [[INT<0,15>, ...], ...],
        ...
    ],
    "state": Enum<NOT_FINISHED, WIN, GAME_OVER>,
    "score": INT<0,254>,
    "action_input": {
        "id": 6
        "data": {
            "x": :x,
            "y": :y
        }
    },
}
```

## Environment Settings

You can change local settings (eg. what games available) via the `.env` file. Copy `.env-example` to `.env` first to make changes.

## Contributing

Install dev dependencies:

```bash
uv sync
```

Activate your development env:

```bash
source .venv/bin/activate
```

Finally install git hooks:

```bash
pre-commit install
```

You're now ready to contribute! This repo uses [`ruff`](https://github.com/astral-sh/ruff) to lint and format code and [`mypy`](https://github.com/python/mypy) for static type checking. You can run all of the tools manually like this:

```bash
pre-commit run --all-files
```

Note: by default these tools will run automatically before `git commit`. It's also recommended to set up `ruff` [inside your IDE](https://docs.astral.sh/ruff/editors/setup/).

## Tests

Work In Progress