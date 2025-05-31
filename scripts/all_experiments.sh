#! /bin/bash

################################################################################################
#                                     Main Experiments (Table 1)                               #
################################################################################################

# Doom 2
python main.py --game doom2 --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game doom2 --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game doom2 --model gpt-4o --enable-ui
python main.py --game doom2 --model claude-3.7 --enable-ui
python main.py --game doom2 --model llama4 --enable-ui --max-context-size 10

# Civilization
python main.py --game civ --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game civ --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game civ --model gpt-4o --enable-ui
python main.py --game civ --model claude-3.7 --enable-ui
python main.py --game civ --model llama4 --enable-ui --max-context-size 10

# Need for Speed
python main.py --game need_for_speed --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game need_for_speed --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game need_for_speed --model gpt-4o --enable-ui
python main.py --game need_for_speed --model claude-3.7 --enable-ui
python main.py --game need_for_speed --model llama4 --enable-ui --max-context-size 10

# The Incredible Machine
python main.py --game incredible-machine --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game incredible-machine --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game incredible-machine --model gpt-4o --enable-ui
python main.py --game incredible-machine --model claude-3.7 --enable-ui
python main.py --game incredible-machine --model llama4 --enable-ui --max-context-size 10

# Pokemon Crystal
python main.py --game pokemon_crystal --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game pokemon_crystal --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game pokemon_crystal --model gpt-4o --enable-ui
python main.py --game pokemon_crystal --model claude-3.7 --enable-ui
python main.py --game pokemon_crystal --model llama4 --enable-ui --max-context-size 10

# Zelda
python main.py --game zelda --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game zelda --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game zelda --model gpt-4o --enable-ui
python main.py --game zelda --model claude-3.7 --enable-ui
python main.py --game zelda --model llama4 --enable-ui --max-context-size 10

# Kirby
python main.py --game kirby --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui
python main.py --game kirby --model gemini-2.0-flash --max-tokens 2048 --enable-ui
python main.py --game kirby --model gpt-4o --enable-ui
python main.py --game kirby --model claude-3.7 --enable-ui
python main.py --game kirby --model llama4 --enable-ui --max-context-size 10


################################################################################################
#                                     Lite Experiments (Table 2)                               #
################################################################################################
python main.py --game doom2 --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui --lite
python main.py --game doom2 --model gemini-2.0-flash --max-tokens 2048 --enable-ui --lite
python main.py --game doom2 --model gpt-4o --enable-ui --lite
python main.py --game doom2 --model claude-3.7 --enable-ui --lite
python main.py --game doom2 --model llama4 --enable-ui --lite --max-context-size 10

# Zelda
python main.py --game zelda --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui --lite
python main.py --game zelda --model gemini-2.0-flash --max-tokens 2048 --enable-ui --lite
python main.py --game zelda --model gpt-4o --enable-ui --lite
python main.py --game zelda --model claude-3.7 --enable-ui --lite
python main.py --game zelda --model llama4 --enable-ui --lite --max-context-size 10

# Kirby
python main.py --game kirby --model gemini/gemini-2.5-pro-preview-03-25 --max-tokens 2048 --enable-ui --lite
python main.py --game kirby --model gemini-2.0-flash --max-tokens 2048 --enable-ui --lite
python main.py --game kirby --model gpt-4o --enable-ui --lite
python main.py --game kirby --model claude-3.7 --enable-ui --lite
python main.py --game kirby --model llama4 --enable-ui --lite --max-context-size 10


################################################################################################
#                                   Practice Game Experiments (Table 3)                        #
################################################################################################
python main.py --game calibration_navigation --model gemini/gemini-2.5-pro-preview-03-25 --enable-ui
python main.py --game calibration_navigation --model gemini-2.0-flash --enable-ui
python main.py --game calibration_navigation --model gpt-4o --enable-ui
python main.py --game calibration_navigation --model claude-3.7 --enable-ui
python main.py --game calibration_navigation --model llama4 --enable-ui --max-context-size 10

python main.py --game calibration_clicking --model gemini/gemini-2.5-pro-preview-03-25 --enable-ui
python main.py --game calibration_clicking --model gemini-2.0-flash --enable-ui
python main.py --game calibration_clicking --model gpt-4o --enable-ui
python main.py --game calibration_clicking --model claude-3.7 --enable-ui
python main.py --game calibration_clicking --model llama4 --enable-ui --max-context-size 10

python main.py --game calibration_dragging --model gemini/gemini-2.5-pro-preview-03-25 --enable-ui
python main.py --game calibration_dragging --model gemini-2.0-flash --enable-ui
python main.py --game calibration_dragging --model gpt-4o --enable-ui
python main.py --game calibration_dragging --model claude-3.7 --enable-ui
python main.py --game calibration_dragging --model llama4 --enable-ui --max-context-size 10
