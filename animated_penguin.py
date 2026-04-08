#!/usr/bin/env python3
"""Animated ASCII penguin."""

import subprocess
import time
import sys

FRAMES = [
    # Frame 1 - standing
    r"""
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
    """,
    # Frame 2 - waving right
    r"""
       .--.
      |o_o |  /
      |:_/ | /
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
    """,
    # Frame 3 - standing
    r"""
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
    """,
    # Frame 4 - waving left
    r"""
       .--.
  \   |o_o |
   \  |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
    """,
    # Frame 5 - looking right
    r"""
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/  ~
    """,
    # Frame 6 - looking left
    r"""
       .--.
      |o_o |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
 ~ \___)=(___/
    """,
    # Frame 7 - happy
    r"""
       .--.
      |^_^ |
      |:_/ |
     //   \ \
    (|     | )
   /'\_   _/`\
   \___)=(___/
    """,
    # Frame 8 - waddling right
    r"""
        .--.
       |o_o |
       |:_/ |
      //   \ \
     (|     | )
    /'\_   _/`\
    \___)=(___/
    """,
    # Frame 9 - waddling left
    r"""
      .--.
     |o_o |
     |:_/ |
    //   \ \
   (|     | )
  /'\_   _/`\
  \___)=(___/
    """,
]

def clear_screen():
    subprocess.run(["clear"], check=False)

def animate():
    print("Animated Penguin! Press Ctrl+C to stop.\n")
    time.sleep(1)
    try:
        while True:
            for frame in FRAMES:
                clear_screen()
                print("\033[96m" + frame + "\033[0m")  # cyan color
                print("  Penguin vibes!")
                time.sleep(0.4)
    except KeyboardInterrupt:
        clear_screen()
        print("\n  Bye!\n")
        sys.exit(0)

if __name__ == "__main__":
    animate()
