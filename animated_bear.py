"""Animated bear — run in your terminal for a rainbow dancing bear."""

import sys
import time

FRAMES = [
    r"""
      ʕ •ᴥ•ʔ
     ⊂  つ
      |  |
     ⊂_⊃ ⊂_⊃
    """,
    r"""
      ʕ •ᴥ•ʔ
    ⊂    つ
      |  |
    ⊂_⊃  ⊂_⊃
    """,
    r"""
      ʕ •ᴥ•ʔ
       ⊂つ
      |  |
       ⊂⊃
    """,
    r"""
      ʕ •ᴥ•ʔ
      ⊂  つ
     /|  |\
    ⊂_⊃  ⊂_⊃
    """,
    r"""
      ʕ >ᴥ<ʔ
     \⊂  つ/
      |  |
     ⊂_⊃ ⊂_⊃
    """,
    r"""
      ʕ •ᴥ•ʔ
      ⊂  つ
      |  |
    _/ ⊃⊂ \_
    """,
    r"""
      ʕ ≧ᴥ≦ʔ
      ⊂  つ
     \|  |/
     ⊂_⊃ ⊂_⊃
    """,
    r"""
      ʕ •ᴥ•ʔ
       ⊂つ
       ||
      ⊂⊃⊂⊃
    """,
]

RAINBOW = [
    "\033[91m",  # red
    "\033[38;5;208m",  # orange
    "\033[93m",  # yellow
    "\033[92m",  # green
    "\033[96m",  # cyan
    "\033[94m",  # blue
    "\033[95m",  # magenta
    "\033[38;5;201m",  # pink
]
RESET = "\033[0m"
BOLD = "\033[1m"
CLEAR = "\033[2J\033[H"


def rainbow_text(text, offset=0):
    """Color each non-space character in a cycling rainbow."""
    result = []
    color_idx = offset
    for ch in text:
        if ch in (" ", "\n"):
            result.append(ch)
        else:
            result.append(f"{BOLD}{RAINBOW[color_idx % len(RAINBOW)]}{ch}{RESET}")
            color_idx += 1
    return "".join(result)


def animate(loops=50, fps=4):
    delay = 1.0 / fps
    print("\033[?25l", end="")  # hide cursor
    try:
        for i in range(loops):
            print(CLEAR, end="")
            frame = FRAMES[i % len(FRAMES)]
            print(f"\n{rainbow_text(frame, offset=i)}")
            bar = "♪ ♫ ♪ " * ((i % 4) + 1)
            print(f"  {rainbow_text(bar, offset=i + 3)}\n")
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h", end="")  # show cursor
        print(f"\n  {BOLD}\033[95mʕ •ᴥ•ʔ bye bye!{RESET}\n")


if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    animate(loops=loops)
