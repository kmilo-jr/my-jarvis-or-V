from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EndpointEvent:
    started: bool = False
    ended: bool = False
    required_silence: float = 0.0


class AdaptiveEndpointDetector:
    """Small streaming endpoint detector used by Voice Input 2.0.

    The detector intentionally works on already-computed speech/quiet decisions,
    keeping it independent from the microphone backend. That makes the timing
    logic deterministic and easy to regression-test.
    """

    def __init__(
        self,
        *,
        block_seconds: float,
        start_blocks: int = 2,
        min_phrase_seconds: float = 0.25,
        short_end_silence_seconds: float = 0.38,
        long_end_silence_seconds: float = 0.46,
        long_phrase_after_seconds: float = 1.40,
    ):
        self.block_seconds = max(0.005, float(block_seconds))
        self.start_blocks = max(1, int(start_blocks))
        self.min_phrase_seconds = max(0.0, float(min_phrase_seconds))
        self.short_end_silence_seconds = max(self.block_seconds, float(short_end_silence_seconds))
        self.long_end_silence_seconds = max(self.short_end_silence_seconds, float(long_end_silence_seconds))
        self.long_phrase_after_seconds = max(self.min_phrase_seconds, float(long_phrase_after_seconds))
        self.speaking = False
        self.ended = False
        self.hot_count = 0
        self.quiet_time = 0.0
        self.speech_time = 0.0
        self.blocks_seen = 0
        self.start_block = None
        self.end_block = None

    @property
    def required_silence(self) -> float:
        if self.speech_time >= self.long_phrase_after_seconds:
            return self.long_end_silence_seconds
        return self.short_end_silence_seconds

    def push(self, *, hot: bool, quiet: bool) -> EndpointEvent:
        if self.ended:
            return EndpointEvent(ended=True, required_silence=self.required_silence)

        self.blocks_seen += 1
        event = EndpointEvent(required_silence=self.required_silence)

        if not self.speaking:
            if hot:
                self.hot_count += 1
            else:
                self.hot_count = 0
            if self.hot_count >= self.start_blocks:
                self.speaking = True
                self.start_block = self.blocks_seen
                # Count the trigger blocks as part of the utterance.
                self.speech_time = self.start_blocks * self.block_seconds
                self.quiet_time = 0.0
                event.started = True
            return event

        self.speech_time += self.block_seconds
        if quiet:
            self.quiet_time += self.block_seconds
        else:
            self.quiet_time = 0.0

        event.required_silence = self.required_silence
        if self.speech_time >= self.min_phrase_seconds and self.quiet_time + 1e-9 >= self.required_silence:
            self.ended = True
            self.end_block = self.blocks_seen
            event.ended = True
        return event
