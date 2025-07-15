# ARC-AGI-3-Agents

## Quickstart

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if not aready installed.

1. Clone the ARC-AGI-3-Agents repo and enter the directory.

```bash
git clone https://github.com/arcprize/ARC-AGI-3-Agents.git
cd ARC-AGI-3-Agents
```

2. Copy .env-example to .env

```bash
cp .env-example .env
```

3. Get an API key from the [ARC-AGI-3 Website](https://three.arcprize.org/) and set it as an environment variable in your .env file.

```bash
export ARC_API_KEY="your_api_key_here"
```

4. Run the random agent (generates random actions) against the locksmith game.

```bash
uv run main.py --agent=random --game=locksmith
```

For more information, see the [documentation](https://three.arcprize.org/docs#quick-start).

## Content submission

To submit your agent for the ARC-AGI-3 competition, please use this form: https://forms.gle/wMLZrEFGDh33DhzV9.

## Contributing

WIP

## Tests

To run the tests, you will need to have `pytest` installed.

```bash
pytest
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.