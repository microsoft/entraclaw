#!/usr/bin/env python3
"""Animated ASCII cat that lounges around your terminal."""

import subprocess
import sys
import time

FRAMES = [
    r"""
    /\_/\
   ( o.o )
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( -.- )
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( o.o )
    > ^ <
   /|   |\~
  (_|   |_)
    """,
    r"""
    /\_/\
   ( o.o )
    > ^ <
 ~/|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( ^.^ )
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( o.o )  ~meow~
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( -.- )  zzz
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( -.- )  zzzZZZ
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( o.O )  !
    > ^ <
   /|   |\
  (_|   |_)
    """,
    r"""
    /\_/\
   ( o.o )
    > w <
   /|   |\
  (_|   |_)
    """,
]

COLORS = [
    "\033[38;5;213m",  # pink
    "\033[38;5;219m",  # light pink
    "\033[38;5;183m",  # lavender
    "\033[38;5;147m",  # periwinkle
    "\033[38;5;117m",  # sky blue
    "\033[38;5;123m",  # cyan
    "\033[38;5;158m",  # mint
    "\033[38;5;193m",  # lime
    "\033[38;5;229m",  # cream
    "\033[38;5;223m",  # peach
]

RESET = "\033[0m"
BOLD = "\033[1m"


def clear_screen():
    subprocess.run(["clear"], check=False)


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def animate():
    hide_cursor()
    frame_idx = 0
    try:
        while True:
            clear_screen()
            color = COLORS[frame_idx % len(COLORS)]
            frame = FRAMES[frame_idx % len(FRAMES)]

            print(f"\n{BOLD}{color}")
            print("  ╔══════════════════════════╗")
            print("  ║    ~ Terminal Cat ~       ║")
            print("  ╚══════════════════════════╝")
            print(frame)
            print(f"  frame {frame_idx % len(FRAMES) + 1}/{len(FRAMES)}")
            print(f"  [Ctrl+C to quit]{RESET}")

            frame_idx += 1
            time.sleep(0.6)
    except KeyboardInterrupt:
        clear_screen()
        show_cursor()
        print(f"\n{BOLD}{COLORS[2]}")
        print(r"    /\_/\ ")
        print(r"   ( ^.^ )  bye!")
        print(r"    > ^ <")
        print(f"{RESET}\n")


if __name__ == "__main__":
    animate()
