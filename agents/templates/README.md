# Agent Templates

This directory contains template files to help developers quickly build custom agents to run on ARC-AGI-3.

## Quick Start Guide

### Building a Simple Agent

1. **Copy the random agent template:**
   ```bash
   cp agents/templates/random_agent.py agents/my_agent.py
   ```

2. **Customize your agent:**
   ```python
   class MyAgent(Agent):
       MAX_ACTIONS = 80
       
       def is_done(self, frames, latest_frame):
           # Define when your agent should stop
           return latest_frame.state == GameState.WIN
       
       def choose_action(self, frames, latest_frame):
           # Implement your decision logic
           return GameAction.ACTION1
   ```

3. **Register your agent:**
   Add to `agents/__init__.py`:
   ```python
   from .my_agent import MyAgent
   
   AVAILABLE_AGENTS = {
       # ... existing agents ...
       "myagent": MyAgent,
   }
   ```

4. **Run your agent:**
   ```bash
   uv run main.py --agent=myagent --game=locksmith
   ```

### Building an LLM Agent

1. **Set up OpenAI API:**
   ```bash
   # Add to your .env file
   OPENAI_SECRET_KEY=your_api_key_here
   ```

2. **Copy the LLM template:**
   ```python
   from agents.templates.llm_agents import LLM
   
   class MyLLMAgent(LLM):
       MODEL = "gpt-4o-mini"
       MAX_ACTIONS = 80
       
       def build_user_prompt(self, latest_frame):
           # Customize the prompt for your specific game
           return "Your custom game instructions here..."
   ```

3. **Register and run:**
   Same as above, but use your LLM agent class.

### Building a Reasoning LLM Agent

1. **Set up OpenAI API:**
   ```bash
   # Add to your .env file
   OPENAI_SECRET_KEY=your_api_key_here
   ```

2. **Use the ReasoningLLM template (o4-mini):**
   ```python
   from agents.templates.llm_agents import ReasoningLLM
   
   class MyReasoningAgent(ReasoningLLM):
       # Uses o4-mini by default
       MAX_ACTIONS = 80
       
       def build_user_prompt(self, latest_frame):
           return "Complex reasoning task instructions..."
   ```

3. **Register and run:**
   Same as above, but use your ReasoningLLM agent class.

Example reasoning field content: (this is the reasoning field in the API response)
   
   ```json
   {
     "model": "o4-mini",
     "action_chosen": "ACTION2",
     "reasoning_tokens_last_response": 150,
     "total_reasoning_tokens_session": 850,
     "game_context": {
       "score": 3,
       "state": "NOT_FINISHED",
       "action_counter": 15
     },
     "decision_summary": "Selected ACTION2 based on o4-mini reasoning"
   }
   ```

The reasoning field is opaque and supports any valid JSON.

## Agent Class Methods

### Required Methods to Override
- `is_done(frames, latest_frame)`: Decide when to stop playing
- `choose_action(frames, latest_frame)`: Select the next action

### Optional Methods to Override
- `name`: Property that returns the agent's display name
- `cleanup()`: Called when the agent finishes playing
- For LLM agents:
  - `build_user_prompt()`: Customize the LLM prompt
  - `build_func_resp_prompt()`: Customize observation prompts
