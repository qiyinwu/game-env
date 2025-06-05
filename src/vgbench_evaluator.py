"""Evaluator for running LLM game interactions on VideoGameBench."""
from typing import Dict, Any, Optional, List, Callable
import time
import random
import asyncio
from PIL import Image
import io
from abc import ABC, abstractmethod

from src.llm.utils import convert_from_dict
from src.llm.vgagent import GameBoyVGAgent, WebBrowsingVGAgent
from src.consts import NO_OP_SKIP_FRAMES
from src.emulators.gba.interface import GBAInterface
from src.emulators.dos.website_server import DOSGameServer
from src.emulators.dos.interface import DOSGameInterface
from src.utils import is_same_hash, hash_image, dist_hash

class BaseVGBenchEvaluator(ABC):
    """Abstract base class for evaluators that coordinate between game emulators and LLMs."""
    
    def __init__(
        self, 
        max_steps: int = 1000,
        step_delay: float = 0.0,
        metrics: Optional[List[Callable]] = None,
        checkpoints: Optional[List[str]] = None,
        threshold: Optional[float] = None
    ):
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.metrics = metrics or []
        self.checkpoints = checkpoints
        self.threshold = threshold if threshold else 10

        # Add checkpoint tracking
        self.current_checkpoint_idx = 0 if checkpoints else None
        self.completed_checkpoints = set()

    @abstractmethod
    async def run_episode(self, agent) -> Dict[str, Any]:
        """Run an episode of the game."""
        pass

    def _check_checkpoint_progress(self, obs, agent) -> bool:
        """Helper method to check and update checkpoint progress."""
        if not self.checkpoints or self.current_checkpoint_idx is None or isinstance(obs, dict):
            return False
            
        # Check if we've reached the current or any future checkpoint
        obs_hash = hash_image(obs)
        for idx in range(self.current_checkpoint_idx, len(self.checkpoints)):
            if is_same_hash(obs_hash, 
                            self.checkpoints[idx], 
                            threshold=self.threshold, 
                            verbose=False):
                self.completed_checkpoints.add(self.checkpoints[idx])
                self.current_checkpoint_idx = idx + 1
                # Notify agent of checkpoint progress
                agent.update_checkpoint(idx+1)
                print(f"Checkpoint {idx+1} completed!", self.threshold)
                # Return True if we've reached the final checkpoint
                return idx == len(self.checkpoints) - 1
        return False

class GBEvaluator(BaseVGBenchEvaluator):
    """Evaluator class that coordinates between GB
     emulators (e.g. Game Boy) and LLMs."""
    
    def __init__(
        self, 
        game_interface: GBAInterface,
        max_steps: int = 1000,
        step_delay: float = 0.1,
        skip_frames: int = 1,
        metrics: Optional[List[Callable]] = None,
        fake_actions: bool = False,
        action_frames: int = 30,
        checkpoints: Optional[List[str]] = None,
        threshold: float = 10
    ):
        super().__init__(max_steps, step_delay, metrics, checkpoints, threshold)
        self.game = game_interface
        self.fake_actions = fake_actions
        self.skip_frames = skip_frames
        self.action_frames = action_frames
    

    async def run_episode(self, agent: GameBoyVGAgent, lite: bool = False) -> Dict[str, Any]:
        """Run an episode of the game.
        
        Args:
            agent: The agent to use for the episode.
            
        Returns:
            Dict containing evaluation metrics.
        """
        if lite:
            return await self.run_episode_lite(agent)
        else:
            return await self.run_episode_realtime(agent)



    async def run_episode_lite(self, gba_agent: GameBoyVGAgent) -> Dict[str, Any]:
        """
        Run an episode of a game using the Gym-based emulator and interacting with it
        at the frame level. The game pauses when the LLM is thinking.

        Part of VG-Bench Lite.
        """
        # Initialize agent's checkpoint tracking
        if self.checkpoints:
            gba_agent.setup_checkpoints(len(self.checkpoints))
        
        try:
            # Get initial observation
            obs = self.game.get_observation()
            gba_agent.store_observation(obs, action_step=0)

            # Initialize action list
            actions_to_run = []

            # Main loop
            for step in range(self.max_steps):
                # Get new actions if needed
                if not actions_to_run:
                    actions_to_run = await gba_agent.get_action()

                # Get next action from list
                action = actions_to_run.pop(0) if actions_to_run else None
                if action is None:
                    obs, _, _, _ = self.game.no_op(self.action_frames)
                else: 
                    obs, _, _, _ = self.game.step(action, self.action_frames)

                # Update observation with current step number
                gba_agent.store_observation(obs, action_step=step+1)
                # Check checkpoint progress
                if self._check_checkpoint_progress(obs["screen"], gba_agent):
                    print("Task complete! All checkpoints completed.")
                    
        except KeyboardInterrupt:
            print("\nEvaluation interrupted by user")
        except Exception as e:
            print(f"Error during evaluation: {e}")
        finally:
            self.game.close()
            
        return

    async def run_episode_realtime(self, gba_agent: GameBoyVGAgent) -> Dict[str, Any]:
        """
        Run an episode of a game using the Gym-based emulator with LLM interacting
        in realtime, e.g. async calls to get actions and observations.

        Part of VG-Bench
        """
        # Initialize agent's checkpoint tracking
        if self.checkpoints:
            gba_agent.setup_checkpoints(len(self.checkpoints))
        
        try:
            # Get initial observation
            obs = self.game.get_observation()
            gba_agent.store_observation(obs, action_step=0)

            # Initialize action list and frame counter
            actions_to_run = []
            
            # Main loop
            for step in range(self.max_steps):
                # If we've used all actions, request new ones from LLM
                if not actions_to_run: 
                    action_task = asyncio.create_task(gba_agent.get_action())
                    
                    # Call no_op() while waiting for the LLM response
                    while not action_task.done():
                        obs, _, _, _ = self.game.no_op(1)
                        if self._check_checkpoint_progress(obs["screen"], gba_agent):
                            print("Task complete! All checkpoints completed.")
                        await asyncio.sleep(0.01)
                    
                    # Get the new list of actions
                    actions_to_run = await action_task

                # Bad action parse or not action given, try again
                if not actions_to_run:
                    # Make a no_op step and continue if no valid actions
                    obs, _, _, _ = self.game.no_op(self.action_frames)
                    gba_agent.store_observation(obs, action_step=step+1)

                    if self._check_checkpoint_progress(obs["screen"], gba_agent):
                        print("Task complete! All checkpoints completed.")
                    continue

                # Take step in environment if action is not None
                current_action = actions_to_run.pop(0)
                if current_action is not None:
                    obs, _, _, _ = self.game.step(current_action, self.action_frames)
                else:
                    obs, _, _, _ = self.game.no_op(self.action_frames)
                
                gba_agent.store_observation(obs, action_step=step+1)   

        except KeyboardInterrupt:
            print("\nEvaluation interrupted by user")
        except Exception as e:
            print(f"Error during realtime evaluation: {e}")
        return

class DOSEvaluator(BaseVGBenchEvaluator):
    """Evaluator class that coordinates between DOS emulators and LLMs."""
    
    def __init__(self, 
            max_steps: int = 10000, 
            step_delay: float = 0.1,
            metrics: Optional[List[Callable]] = None,
            checkpoints: Optional[List[str]] = None,
            game_interface: DOSGameInterface = None,
            threshold: float = 10
            ):
        super().__init__(max_steps, step_delay, metrics, checkpoints, threshold)
        self.game = game_interface
    
    async def start(self, url: str):
        # Start the agent
        await self.game.load_game(initial_url=url)

    async def run_episode(self, dos_agent: WebBrowsingVGAgent, task: str, server: DOSGameServer) -> Dict[str, Any]:
        """
        Run an episode of a game using JS-DOS with LLM interacting
        in realtime or paused based on if lite mode is on (controlled in agent).

        """

        # Initialize agent's checkpoint tracking
        if self.checkpoints:
            dos_agent.setup_checkpoints(len(self.checkpoints))

        try:
            # Get initial screenshot
            screen = await self.game.get_observation()
            await dos_agent.store_observation([screen])

            # Main game loop
            task_complete = False
            for step in range(self.max_steps):
                # Get the new list of actions
                action, action_input = await dos_agent.get_action(task, self.game.browser, step)


                # action_task = asyncio.create_task(dos_agent.get_action(task, self.game.browser, step))
                
                # # Call no_op() while waiting for the LLM response
                # while not action_task.done():
                #     frame = await self.game.get_observation()
                #     frame_pil = Image.open(io.BytesIO(frame)).crop((50, 0, 640, 400))
                #     if self._check_checkpoint_progress(frame_pil, dos_agent):
                #         print("Task complete! All checkpoints completed.")
                #     await asyncio.sleep(0.01)
                
                # Get the new list of actions
                # action, action_input = await action_task

                await dos_agent.pre_action(action, action_input, self.game.lite)
                info, frames = await self.game.step(action, action_input)
                await dos_agent.post_action(info, frames, action, action_input)
                
                # Check if the task is complete
                for frame in frames:
                    frame_pil = Image.open(io.BytesIO(frame)).crop((50, 0, 640, 400))
                    if self._check_checkpoint_progress(frame_pil, dos_agent):
                        task_complete = True

                
                if task_complete:
                    # For now, don't want to accidentally end runs if this gets falsely triggered.
                    print("Task complete! All checkpoints completed.")
                    # return

            if step == self.max_steps - 1:
                print("Reached maximum number of steps without completing the task.")
            
            # Execute the task
        finally:
            # Stop the agent
            await self.game.close()
            await dos_agent.stop()
            
            # Stop the server if it was started
            if server:
                server.stop()