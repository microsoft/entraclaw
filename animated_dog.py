#!/usr/bin/env python3
"""Animated ASCII dog — tail wags, walks, pants, and does tricks in color!"""

import subprocess
import time
import sys

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
BROWN = "\033[38;5;137m"
DARK_BROWN = "\033[38;5;94m"
WHITE = "\033[97m"
RED = "\033[91m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"

GROUND = f"  {GREEN}{'~.~' * 12}{RESET}"


def clear():
    subprocess.run(["clear"], check=False)


# --- Scene 1: Tail wagging side-view dog ---
WAGS = [
    r"""
    / \__
   (    @\___
   /         O
  /   (_____/
 /_____/   U
""",
    r"""
     __/\
   (    @\___
   /         o
  /   (_____/
 /_____/   U
""",
    r"""
        |
   (    @\___
   /         O
  /   (___P_/
 /_____/   U
""",
    r"""
     __/\
   (    @\___
    \        o
  /   (_____/
 /_____/ U U
""",
]

# --- Scene 2: Big front-facing dog ---
BIG_DOG = [
    r"""
                  ;\
                 |' \
     _____       ;   \\
    /     \     /    ;;
   | () () |   /    ;;
    \  ^  /  |    ;;
     |||||    \  /;
     |||||     \|
     |||||
     |||||  woof!
    /     \
   /       \
""",
    r"""
              /;
             / ' |
     _____  //   ;
    /     \ /    ;;
   | () () |    ;;
    \  ^  / |  ;;
     |||||   \/;
     |||||    |
     |||||
     |||||
    /     \
   /       \
""",
    r"""
                |
                |
     _____      |
    /     \    /
   | () () |  /
    \  ~  / |/
     |||||  /
     |||||
     |||||
     |||||  arf!
    /     \
   /       \
""",
    r"""
                  ;\
                 |' \
     _____       ;   \\
    /     \     /    ;;
   | () () |   /    ;;
    \  P  /  |    ;;
     |||||    \  /;
     |||||     \|
     |||||
     |||||  *pant*
    /     \
   /       \
""",
]

# --- Scene 3: Walking dog ---
WALK = [
    r"""
     ___
    |   |  /\
    |   |_/  \   __
    |         |_/  |  WOOF!
    |              |
    |    ()   ()   /
     \     __    /
      |   |  |  |
      |   |  |  |
     _/   | _/  |
""",
    r"""
     ___
    |   |  /\
    |   |_/  \   __
    |         |_/  |
    |              |
    |    ()   ()   /
     \     __    /
       \  |   \ |
        | |    ||
       _/ |   _/|
""",
    r"""
     ___
    |   |  /\
    |   |_/  \   __
    |         |_/  |  ARF!
    |              |
    |    ()   ()   /
     \     __    /
      |  |   |  |
      |  |   |  |
      /  |   /  |
""",
    r"""
     ___
    |   |  /\
    |   |_/  \   __
    |         |_/  |
    |              |
    |    ()   ()   /
     \     __    /
      \  |    \ |
       | |     ||
       / |    _/|
""",
]


def colorize(frame):
    """Apply colors to the ASCII dog."""
    c = frame
    c = c.replace("@", f"{YELLOW}@{BROWN}")
    c = c.replace("^", f"{YELLOW}^{BROWN}")
    c = c.replace("~", f"{YELLOW}~{BROWN}")
    c = c.replace("P", f"{RED}P{BROWN}")
    c = c.replace("()", f"{WHITE}(){BROWN}")
    return f"{BROWN}{c}{RESET}"


def play_scene(frames, label, cycles=3, fps=4):
    """Animate one scene."""
    delay = 1.0 / fps
    for cycle in range(cycles):
        for i, frame in enumerate(frames):
            clear()
            print(f"\n  {CYAN}{BOLD}=== {label} ==={RESET}\n")
            print(colorize(frame))
            print(GROUND)
            print(f"\n  {CYAN}cycle {cycle+1}/{cycles}  |  ctrl+c to quit{RESET}")
            time.sleep(delay)


def finale():
    clear()
    print(colorize(r"""

     _____
    /     \       GOOD BOY!
   | () () |
    \  ^  /    ____
     |||||    / __ \
     |||||   | |  | |
     |||||   | |__| |
    /|| ||\   \____/
   / || || \
"""))
    print(GROUND)
    print(f"\n  {CYAN}{BOLD}Animation complete!{RESET}\n")


def main():
    try:
        print(f"\n  {BROWN}{BOLD}ASCII Dog Animation{RESET}")
        print(f"  {CYAN}Press Ctrl+C to exit at any time{RESET}\n")
        time.sleep(1)

        play_scene(WAGS, "Tail Wagging", cycles=3, fps=4)
        play_scene(BIG_DOG, "Big Happy Dog", cycles=3, fps=3)
        play_scene(WALK, "Walkies!", cycles=4, fps=4)
        finale()

    except KeyboardInterrupt:
        clear()
        print(f"\n  {BROWN}Woof! Goodbye!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
