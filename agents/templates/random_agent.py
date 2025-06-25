import random
from typing import Any

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState


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
        elif action.is_complex():
            action.set_data(
                {
                    "game_id": self.game_id,
                    "x": random.randint(0, 63),
                    "y": random.randint(0, 63),
                }
            )
        return action


# Example of a simple custom agent you can build
class MyCustomAgent(Agent):
    """Template for creating your own custom agent."""
    
    MAX_ACTIONS = 200
    
    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Customize this method to define when your agent should stop."""
        return latest_frame.state in [GameState.WIN, GameState.GAME_OVER]
    
    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Customize this method to implement your agent's decision logic."""
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            action = GameAction.RESET
            action.set_data({"game_id": self.game_id})
        else:
            # Add your custom logic here
            # For now, just do ACTION1 as an example
            action = GameAction.ACTION1
            action.set_data({"game_id": self.game_id})
        
        return action 