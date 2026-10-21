from __future__ import annotations
import unittest
from voice.endpoint import AdaptiveEndpointDetector


class VoiceInputV2Tests(unittest.TestCase):
    BLOCK = 0.03

    def make(self):
        return AdaptiveEndpointDetector(
            block_seconds=self.BLOCK,
            start_blocks=2,
            min_phrase_seconds=0.30,
            short_end_silence_seconds=0.38,
            long_end_silence_seconds=0.46,
            long_phrase_after_seconds=1.40,
        )

    def feed(self, det, seconds, *, speech):
        n = round(seconds / self.BLOCK)
        events=[]
        for _ in range(n):
            events.append(det.push(hot=speech, quiet=not speech))
        return events

    def test_single_30ms_noise_spike_does_not_start(self):
        d=self.make()
        d.push(hot=True,quiet=False)
        d.push(hot=False,quiet=True)
        self.assertFalse(d.speaking)

    def test_speech_starts_within_60ms(self):
        d=self.make()
        e1=d.push(hot=True,quiet=False)
        e2=d.push(hot=True,quiet=False)
        self.assertFalse(e1.started)
        self.assertTrue(e2.started)
        self.assertTrue(d.speaking)

    def test_short_command_ends_quickly(self):
        d=self.make()
        self.feed(d,0.75,speech=True)
        self.assertTrue(d.speaking)
        # 360 ms is not enough, 390 ms is.
        self.feed(d,0.36,speech=False)
        self.assertFalse(d.ended)
        self.feed(d,0.03,speech=False)
        self.assertTrue(d.ended)

    def test_300ms_pause_inside_sentence_is_preserved(self):
        d=self.make()
        self.feed(d,0.72,speech=True)
        self.feed(d,0.30,speech=False)
        self.assertFalse(d.ended)
        self.feed(d,0.72,speech=True)
        self.assertFalse(d.ended)

    def test_long_sentence_allows_longer_pause(self):
        d=self.make()
        self.feed(d,1.50,speech=True)
        self.feed(d,0.42,speech=False)
        self.assertFalse(d.ended)
        self.feed(d,0.06,speech=False)
        self.assertTrue(d.ended)

    def test_middle_hysteresis_resets_quiet_counter(self):
        d=self.make()
        self.feed(d,0.8,speech=True)
        self.feed(d,0.24,speech=False)
        d.push(hot=False,quiet=False)  # in-between threshold: possible weak speech
        self.feed(d,0.24,speech=False)
        self.assertFalse(d.ended)


if __name__ == '__main__':
    unittest.main(verbosity=2)
