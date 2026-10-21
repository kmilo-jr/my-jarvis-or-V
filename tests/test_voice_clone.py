import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from voice.voice_clone import VoiceCloneSetupError, register_voice_from_sample


class VoiceCloneTests(unittest.TestCase):
    def sample(self, folder):
        path = Path(folder) / "sample.mp3"
        path.write_bytes(b"fake mp3")
        return path

    def test_missing_key_never_sends_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Mock()
            with patch("voice.voice_clone.load_key", return_value=""):
                with self.assertRaisesRegex(VoiceCloneSetupError, "Chave ElevenLabs"):
                    register_voice_from_sample(self.sample(folder), {"config_path": str(Path(folder) / "config.json")}, session=session)
            session.post.assert_not_called()

    def test_rejected_provider_keeps_existing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            config_path.write_text(json.dumps({"voice": {"tts_eleven_voice_id": "old"}}), encoding="utf-8")
            session = Mock(); session.post.return_value.status_code = 401; session.post.return_value.text = "bad key"
            with patch("voice.voice_clone.load_key", return_value="secret"):
                with self.assertRaises(VoiceCloneSetupError):
                    register_voice_from_sample(self.sample(folder), {"config_path": str(config_path)}, session=session)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["voice"]["tts_eleven_voice_id"], "old")

    def test_paid_plan_error_is_explained_without_changing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            config_path.write_text(json.dumps({"voice": {"tts_eleven_voice_id": "old"}}), encoding="utf-8")
            response = Mock(status_code=400)
            response.json.return_value = {"detail": {"status": "can_not_use_instant_voice_cloning", "code": "paid_plan_required"}}
            session = Mock(); session.post.return_value = response
            with patch("voice.voice_clone.load_key", return_value="secret"):
                with self.assertRaisesRegex(VoiceCloneSetupError, "não permite clonagem instantânea"):
                    register_voice_from_sample(self.sample(folder), {"config_path": str(config_path)}, session=session)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["voice"]["tts_eleven_voice_id"], "old")

    def test_success_saves_new_voice_id_and_uses_multipart(self):
        with tempfile.TemporaryDirectory() as folder:
            config_path = Path(folder) / "config.json"
            config_path.write_text(json.dumps({"voice": {"tts_eleven_voice_id": "old"}}), encoding="utf-8")
            response = Mock(status_code=200); response.json.return_value = {"voice_id": "new-id"}
            session = Mock(); session.post.return_value = response
            with patch("voice.voice_clone.load_key", return_value="secret"):
                result = register_voice_from_sample(self.sample(folder), {"config_path": str(config_path)}, session=session)
            self.assertEqual(result["voice_id"], "new-id")
            cfg = json.loads(config_path.read_text(encoding="utf-8"))["voice"]
            self.assertEqual(cfg["tts_eleven_voice_id"], "new-id")
            self.assertEqual(cfg["tts_voice_preset"], "v_prime")
            self.assertIn("files", session.post.call_args.kwargs)
            upload = session.post.call_args.kwargs["files"]["files"]
            self.assertEqual(upload[0], "sample.mp3")


if __name__ == "__main__": unittest.main()
