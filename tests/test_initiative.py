import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import datetime
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from core.initiative import InitiativeStore
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from ui.initiative import InitiativeDialog
from voice.engine import VoiceEngine


class InitiativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = InitiativeStore(Path(self.temp.name) / "initiative.json")
        self.now = datetime(2026, 9, 23, 14).timestamp()
        self.store.update_settings({"quiet_enabled": False})

    def tearDown(self):
        self.temp.cleanup()

    def due(self, title="Revisar projeto"):
        return self.store.add(title, self.now - 10, now=self.now - 20)

    def test_due_delivery_is_persistent_and_not_repeated(self):
        item = self.due()
        self.assertEqual(self.store.next_notice(busy=False, now=self.now)["id"], item["id"])
        self.store.delivered(item["id"], now=self.now)
        reopened = InitiativeStore(self.store.path)
        self.assertIsNone(reopened.next_notice(busy=False, now=self.now + 500))

    def test_busy_pause_and_disabled_defer_without_losing(self):
        self.due()
        self.assertIsNone(self.store.next_notice(busy=True, now=self.now))
        self.store.update_settings({"paused_until": self.now + 3600})
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now))
        self.store.update_settings({"paused_until": 0, "enabled": False})
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now))
        self.store.update_settings({"enabled": True})
        self.assertIsNotNone(self.store.next_notice(busy=False, now=self.now))

    def test_quiet_hours_cross_midnight_and_boundaries(self):
        cfg = self.store.defaults()
        for hour in (22, 23, 0, 7):
            self.assertTrue(self.store.quiet(cfg, datetime(2026, 9, 23, hour).timestamp()))
        for hour in (8, 14, 21):
            self.assertFalse(self.store.quiet(cfg, datetime(2026, 9, 23, hour).timestamp()))
        cfg.update(quiet_start=9, quiet_end=17)
        self.assertTrue(self.store.quiet(cfg, self.now))
        cfg.update(quiet_start=9, quiet_end=9)
        self.assertTrue(self.store.quiet(cfg, self.now))

    def test_gap_and_category_controls(self):
        first = self.due("Primeiro"); self.due("Segundo")
        self.store.delivered(first["id"], now=self.now)
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 119))
        self.assertIsNotNone(self.store.next_notice(busy=False, now=self.now + 120))
        self.store.update_settings({"reminders": False})
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 120))

    def test_breaks_only_after_work_and_no_duplicate_backlog(self):
        self.store.schedule_break(self.now)
        self.assertEqual(self.store.snapshot()["events"], [])
        self.store.work_session(True, self.now)
        self.store.schedule_break(self.now + 2999)
        self.assertEqual(self.store.snapshot()["events"], [])
        self.store.schedule_break(self.now + 3000)
        self.store.schedule_break(self.now + 6000)
        self.assertEqual(len(self.store.snapshot()["events"]), 1)
        self.store.work_session(False)
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 6000))

    def test_summary_counts_real_local_reminders_and_replaces_pending(self):
        self.due()
        self.store.add("Depois", self.now + 3600, now=self.now)
        self.store.startup_summary(self.now)
        self.store.startup_summary(self.now)
        pending = [e for e in self.store.snapshot()["events"] if e["kind"] == "summaries" and e["state"] == "pending"]
        self.assertEqual(len(pending), 1)
        self.assertIn("1 lembrete(s) vencido(s) e 1", pending[0]["title"])

    def test_cancel_and_snooze(self):
        item = self.due()
        self.store.change_event(item["id"])
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now))
        future = time.time() + 600
        self.store.change_event(item["id"], due=future)
        self.assertIsNone(self.store.next_notice(busy=False, now=future - 1))
        self.assertIsNotNone(self.store.next_notice(busy=False, now=future))

    def test_invalid_config_preserves_file(self):
        original = self.store.path.read_text(encoding="utf-8")
        for values in ({"gap_seconds": 0}, {"quiet_start": 24}, {"voice": "yes"}):
            with self.assertRaises(ValueError): self.store.update_settings(values)
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), original)
        self.store.path.write_text("broken", encoding="utf-8")
        with self.assertRaises(ValueError): self.store.next_notice(busy=False)
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), "broken")


class InitiativeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = InitiativeStore(Path(self.temp.name) / "initiative.json")
        self.store.update_settings({"quiet_enabled": False})
        self.voice = VoiceEngine({}); self.voice.speak = Mock()
        with patch.object(MainWindow, "_load_mics"):
            self.w = InstagramExperimentWindow(SimpleNamespace(initiative_store=self.store), SimpleNamespace(skills=[]), self.voice, startup_greeting=False)
        self.w.processing_sound.set_enabled(False)
        self.w.append_v = Mock()
        self.w._show_desktop_notice = Mock()

    def tearDown(self):
        self.w.close(); self.w.deleteLater(); self.temp.cleanup()

    def due(self):
        now = time.time()
        self.store.add("Meu lembrete", now - 1, now=now - 2)

    def test_visual_default_and_no_duplicate(self):
        self.due(); self.w._poll_initiative(); self.w._poll_initiative()
        self.w.append_v.assert_called_once()
        self.voice.speak.assert_not_called()

    def test_recording_and_followup_do_not_get_interrupted(self):
        self.due(); self.store.update_settings({"voice": True})
        self.w._voice_capture_busy = True; self.w._poll_initiative()
        self.voice.speak.assert_not_called()
        self.w._voice_capture_busy = False
        self.w._conversation.wait_for_reply(); self.w._conversation.open(time.monotonic())
        self.w._poll_initiative(); self.voice.speak.assert_not_called()
        self.w._conversation.cancel(); self.w._poll_initiative()
        self.voice.speak.assert_called_once()

    def test_muted_response_blocks_notice_voice(self):
        self.due(); self.store.update_settings({"voice": True})
        self.w.tts_toggle.setChecked(False); self.w._poll_initiative()
        self.w.append_v.assert_called_once(); self.voice.speak.assert_not_called()

    def test_completion_records_actual_failure_and_starts_work_on_success(self):
        self.w._active_request = "modo trabalho"
        self.w._command_started_at = time.perf_counter() - 12
        self.w._initiative_completion([SimpleNamespace(ok=False, skill="MODO TRABALHO")])
        self.assertEqual(self.store.snapshot()["next_break"], 0)
        self.assertIn("pendências", self.store.snapshot()["events"][0]["title"])
        self.w._initiative_completion([SimpleNamespace(ok=True, skill="MODO TRABALHO")])
        self.assertGreater(self.store.snapshot()["next_break"], time.time())

    def test_dialog_saves_and_adds_reminder(self):
        dialog = InitiativeDialog(self.w, self.store)
        dialog.checks["voice"].setChecked(True); dialog.save()
        self.assertTrue(self.store.snapshot()["settings"]["voice"])
        dialog.title.setText("Revisar o projeto"); dialog.add()
        self.assertEqual(self.store.snapshot()["events"][0]["title"], "Revisar o projeto")
        dialog.close()

    def test_desktop_notice_uses_tray_and_is_hidden_on_close(self):
        with patch("PySide6.QtWidgets.QSystemTrayIcon") as tray:
            tray.isSystemTrayAvailable.return_value = True
            MainWindow._show_desktop_notice(self.w, "Meu lembrete")
            tray.return_value.showMessage.assert_called_once()
            self.w.close()
            tray.return_value.hide.assert_called_once()


if __name__ == "__main__": unittest.main()
