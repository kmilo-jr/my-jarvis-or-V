"""Elapsed-time animation without catch-up loops after a blocked/hidden window."""
import time


class AnimationClock:
    def __init__(self):
        self.reset()

    def reset(self):
        self.previous = time.monotonic()

    def step(self):
        now = time.monotonic()
        elapsed = max(0.0, min(.1, now - self.previous))
        self.previous = now
        return elapsed
