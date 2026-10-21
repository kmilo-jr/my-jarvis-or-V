import unittest
from unittest.mock import Mock
from core.briefing_music import start_music


class BriefingMusicTests(unittest.TestCase):
    def test_shuffles_current_selection_and_verifies_playback(self):
        command = Mock(return_value=(True, {'status': {'uri': 'spotify:track:test',
            'playing': True, 'shuffle': True, 'volume': .5, 'title': 'Song', 'artist': 'Artist'}}))
        result = start_music(command, playlist_uri='')
        self.assertTrue(result['ok'])
        self.assertEqual([call.args[0] for call in command.call_args_list],
                         ['status', 'volume', 'shuffle', 'next', 'play'])
        self.assertEqual(command.call_args_list[1].args[1], {'level': .15})
        self.assertEqual(command.call_args_list[2].args[1], {'enabled': True})
        self.assertIn('Song', result['body'])

    def test_configured_playlist_starts_without_previous_track(self):
        uri = 'spotify:playlist:37i9dQZF1Epxpa7WkAt2RE'
        result = {'status': {'uri': 'spotify:track:test', 'context_uri': uri,
                            'playing': True, 'shuffle': True}}
        command = Mock(side_effect=[(True, {'status': {'volume': .1}})] + [(True, result)] * 5)
        self.assertTrue(start_music(command, playlist_uri=uri)['ok'])
        self.assertEqual(command.call_args_list[2].args, ('play_uri', {'uri': uri}))
        self.assertEqual([c.args[0] for c in command.call_args_list],
                         ['status', 'volume', 'play_uri', 'shuffle', 'next', 'play'])

    def test_wrong_playlist_or_shuffle_is_not_reported_as_success(self):
        uri = 'spotify:playlist:37i9dQZF1Epxpa7WkAt2RE'
        for context, shuffle in [('spotify:playlist:other', True), (uri, False)]:
            command = Mock(return_value=(True, {'status': {'uri': 'spotify:track:x',
                'playing': True, 'context_uri': context, 'shuffle': shuffle}}))
            self.assertFalse(start_music(command, playlist_uri=uri)['ok'])

    def test_never_raises_a_quieter_volume(self):
        command = Mock(return_value=(True, {'status': {'uri': 'spotify:track:test',
            'playing': True, 'shuffle': True, 'volume': .03}}))
        start_music(command, playlist_uri='')
        self.assertEqual(command.call_args_list[1].args[1], {'level': .03})

    def test_missing_selection_does_not_change_playback(self):
        command = Mock(return_value=(True, {'status': {}}))
        self.assertFalse(start_music(command, playlist_uri='')['ok'])
        self.assertEqual(command.call_count, 1)

    def test_failure_does_not_claim_music_started(self):
        for outcome in [(False, {}), (True, {'status': {'uri': 'spotify:track:x'}})]:
            command = Mock(return_value=outcome)
            self.assertFalse(start_music(command, playlist_uri='')['ok'])
        self.assertFalse(start_music(Mock(side_effect=TimeoutError), playlist_uri='')['ok'])


if __name__ == '__main__':
    unittest.main()
