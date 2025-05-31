import os
import sys
from pathlib import Path

def import_gba_modules():
    try:
        from src.emulators.gba.interface import GBAInterface
        from src.llm.vgagent import GameBoyVGAgent
        from src.vgbench_evaluator import GBEvaluator
        from src.consts import ROM_FILE_MAP
        return GBAInterface, GameBoyVGAgent, GBEvaluator, ROM_FILE_MAP
    except ImportError as e:
        print(f"Error importing GBA modules: {e}")
        print("Make sure you have installed the required dependencies for GBA emulation.")
        sys.exit(1)

async def run_gba_emulator(args):
    """Run the GBA emulator with the given arguments."""
    # Import required modules
    GBAInterface, GameBoyVGAgent, GBEvaluator, ROM_FILE_MAP = import_gba_modules()
    
    # Create ROM directory if it doesn't exist
    project_root = Path(__file__).parent.parent
    rom_dir = project_root / "roms"
    rom_dir.mkdir(exist_ok=True)
    
    # Check if ROM name exists in mapping
    if args.game not in ROM_FILE_MAP:
        print(f"Unknown ROM name: {args.game}")
        print(f"Available ROMs: {', '.join(ROM_FILE_MAP.keys())}")
        return
        
    # Get full ROM path
    rom_file = ROM_FILE_MAP[args.game]
    rom_path = rom_dir / rom_file
    
    if not rom_path.exists():
        print(f"Please place the ROM file '{rom_file}' at: {rom_path}")
        print("Note: The ROM file should be an uncompressed .gb or .gbc file")
        return
        
    # Initialize game interface
    render = not args.headless
    game = GBAInterface(render=render)
    
    # Initialize LLM interface based on chosen API and mode
    gba_agent = None
    
    if args.fake_actions:
        # Use GameBoyVGAgent with fake mode instead of separate FakeGameBoyAgent
        print("Using fake random actions (no LLM API calls)")
        gba_agent = GameBoyVGAgent(
            model="fake-model",  # Placeholder model name for fake mode
            api_key="fake-key",  # Placeholder API key for fake mode
            game=args.game,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_history_tokens=args.history_tokens,
            context_window=args.max_context_size,
            realtime=not args.lite,
            enable_ui=args.enable_ui,
            task_prompt=args.task_prompt,
            api_base=args.api_base,
            fake_mode=True  # Enable fake mode
        )
    else:
        # Get API key from args or environment
        api_key = args.api_key
        # Set model based on API if not specified
        model = args.model
        
        # Initialize the realtime GBAAgent
        gba_agent = GameBoyVGAgent(
            model=model,
            api_key=api_key,
            game=args.game,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_history_tokens=args.history_tokens,
            context_window=args.max_context_size,
            realtime=not args.lite,
            enable_ui=args.enable_ui,
            task_prompt=args.task_prompt,
            api_base=args.api_base,
            fake_mode=False  # Disable fake mode for real LLM calls
        )
        print(f"Using VGagent on VideoGameBench with model: {model}")
    
    # Load the game
    print(f"Loading ROM: {rom_path}")
    if not game.load_game(str(rom_path)):
        print("Failed to load ROM")
        game.close()
        return
    
    print("Game loaded successfully!")
    if hasattr(gba_agent, 'log_dir'):
        print(f"Logging to: {gba_agent.log_dir}")
    
    # Create evaluator
    print(f"Running for up to {args.max_steps} steps...")
    print("Checkpoints:", args.checkpoints)
    evaluator = GBEvaluator(
        game_interface=game, 
        max_steps=args.max_steps, 
        step_delay=args.step_delay, 
        skip_frames=args.skip_frames,
        action_frames=args.action_frames,
        fake_actions=args.fake_actions,
        checkpoints=args.checkpoints,
        threshold=args.threshold,
    )
    
    try:
        metrics = await evaluator.run_episode(gba_agent, args.lite)
        
    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user")
    finally:
        print("Cleaning up...")
        game.close()