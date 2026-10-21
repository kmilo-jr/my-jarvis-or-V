import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication,QMainWindow,QStackedWidget,QWidget
from PySide6.QtTest import QTest
from ui.pixel_office import PixelOffice,activity_for

class OfficeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.w=QMainWindow(); self.w.neural=SimpleNamespace(state='READY')
        self.w.game_mode=SimpleNamespace(enabled=False)
        self.w._active_request=''
        self.stack=QStackedWidget();self.w.setCentralWidget(self.stack)
        self.office=PixelOffice(self.w);self.other=QWidget()
        self.stack.addWidget(self.office);self.stack.addWidget(self.other)
        self.w.resize(850,520);self.w.show();self.app.processEvents()
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents()
    def test_activity_routes_and_ready_does_not_fake_work(self):
        for text,expected in [('qual a filosofia de hoje','books'),('me ajude a aprender inglês','books'),
                ('pesquise notícias','desk'),('minha agenda','calendar'),('toque música','music')]:
            self.assertEqual(activity_for(text,'PROCESSING'),expected)
            self.assertEqual(activity_for(text,'READY'),'rest')
    def test_no_frames_hidden_and_resume_snaps_to_current_task(self):
        self.assertTrue(self.office.timer.isActive())
        self.stack.setCurrentWidget(self.other);self.app.processEvents()
        frames=self.office.frame_count
        self.w._active_request='filosofia';self.w.neural.state='PROCESSING'
        QTest.qWait(220)
        self.assertEqual(self.office.frame_count,frames)
        self.assertFalse(self.office.timer.isActive())
        self.stack.setCurrentWidget(self.office);self.app.processEvents()
        self.assertEqual(self.office.activity,'books')
        self.assertEqual((self.office.x,self.office.y),self.office.TARGETS['books'])
        self.assertTrue(self.office.timer.isActive())
    def test_suspension_and_minimize_stop_timer(self):
        self.office.set_suspended(True);self.assertFalse(self.office.timer.isActive())
        self.office.set_suspended(False);self.assertTrue(self.office.timer.isActive())
        self.w.showMinimized();self.app.processEvents();self.office.step()
        self.assertFalse(self.office.timer.isActive())
    def test_background_reused_and_drawing_all_states(self):
        key=self.office._background.cacheKey()
        for action in self.office.TARGETS:
            self.office.activity=action;self.office.x,self.office.y=self.office.TARGETS[action]
            self.office.state='SPEAKING';self.assertFalse(self.office.grab().isNull())
        self.assertEqual(self.office._background.cacheKey(),key)

    def test_cartoon_sprites_transparent_and_reused(self):
        self.assertEqual(len(self.office._sprites),2)
        for row in self.office._sprites:
            self.assertEqual(len(row),4)
            for sprite in row:
                self.assertFalse(sprite.isNull())
                self.assertTrue(sprite.hasAlphaChannel())
                self.assertLessEqual(sprite.width(),144)
        keys=[[s.cacheKey() for s in row] for row in self.office._sprites]
        for action in self.office.TARGETS:
            self.office.activity=action
            self.office.x,self.office.y=self.office.TARGETS[action]
            self.office._route=[]
            self.office._pose_time=2
            self.assertFalse(self.office.grab().isNull())
        self.assertEqual(keys,[[s.cacheKey() for s in row] for row in self.office._sprites])

    def test_idle_routine_never_repeats_and_command_interrupts_sleep(self):
        self.office.advance_idle(9);self.office.sync_activity()
        self.assertIn(self.office.activity,self.office.IDLE_ACTIVITIES)
        first=self.office.activity
        self.office.advance_idle(30);self.office.sync_activity()
        self.assertNotEqual(self.office.activity,first)
        self.office._idle_activity='sleep';self.office.sync_activity(snap=True)
        self.assertEqual(self.office.activity,'sleep')
        self.w._active_request='filosofia';self.w.neural.state='PROCESSING'
        self.office.sync_activity()
        self.assertEqual(self.office.activity,'books')
        self.assertEqual(self.office._route[-1],self.office.TARGETS['books'])
        self.assertEqual(self.office._idle_activity,'rest')

    def test_hidden_idle_time_is_frozen(self):
        self.office._idle_activity='tv';self.office.sync_activity(snap=True)
        remaining=self.office._idle_remaining
        self.stack.setCurrentWidget(self.other);self.app.processEvents()
        self.office.advance_idle(1000)
        self.assertEqual(self.office._idle_remaining,remaining)
        self.stack.setCurrentWidget(self.office);self.app.processEvents()
        self.assertEqual(self.office.activity,'tv')
        self.assertEqual((self.office.x,self.office.y),self.office.TARGETS['tv'])

    def test_fast_command_is_not_missed_and_hidden_tab_discards_visual_tail(self):
        self.w._active_request='fale sobre os filósofos'
        self.office.begin_request(self.w._active_request)
        self.assertEqual(self.office.activity,'books')
        # A reply may finish before the 80 ms rendering tick.
        self.w.neural.state='READY';self.office.step()
        self.assertEqual(self.office.activity,'books')
        self.stack.setCurrentWidget(self.other);self.app.processEvents()
        self.assertEqual(self.office._task_remaining,0)
        self.stack.setCurrentWidget(self.office);self.app.processEvents()
        self.assertNotEqual(self.office.activity,'books')

    def test_cartoon_room_uses_60fps_timer_for_live_screens(self):
        self.w.neural.state='PROCESSING';self.w._active_request='filosofia'
        self.office.sync_activity(snap=True);self.office.step()
        self.assertEqual(self.office.timer.interval(),16)

    def test_room_cache_reused_and_actor_damage_is_local(self):
        self.assertGreater(self.office._background.width(),1000)
        key=self.office._scaled_background.cacheKey()
        self.w.neural.state='PROCESSING';self.w._active_request='filosofia'
        self.office.sync_activity(snap=True)
        QTest.qWait(250)
        self.assertEqual(key,self.office._scaled_background.cacheKey())
        damage=self.office._actor_region()
        self.assertLess(damage.width()*damage.height(),self.office.width()*self.office.height()/4)
        self.w.resize(1000,650);self.app.processEvents()
        self.assertNotEqual(key,self.office._scaled_background.cacheKey())

    def test_real_timer_starts_idle_walk_without_manual_steps(self):
        origin=(self.office.x,self.office.y)
        QTest.qWait(3800)
        self.assertIn(self.office.activity,self.office.IDLE_ACTIVITIES)
        self.assertNotEqual((self.office.x,self.office.y),origin)

    def test_stale_core_label_cannot_freeze_idle_when_real_work_is_finished(self):
        from unittest.mock import Mock
        self.w.command_thread=None;self.w.pending_commands=[]
        self.w.voice_engine=SimpleNamespace(is_speaking=Mock(return_value=False),
                                           has_pending_speech=Mock(return_value=False))
        self.w._voice_capture_busy=False
        for state in ('SPEAKING','PROCESSING','LISTENING','ERROR'):
            self.w.neural.state=state
            self.assertEqual(self.office._effective_state(),'READY')
        self.w.neural.state='SPEAKING'
        origin=(self.office.x,self.office.y)
        QTest.qWait(3800)
        self.assertIn(self.office.activity,self.office.IDLE_ACTIVITIES)
        self.assertNotEqual(origin,(self.office.x,self.office.y))
        self.w.voice_engine.has_pending_speech.return_value=True
        self.assertEqual(self.office._effective_state(),'SPEAKING')
        self.w.voice_engine.has_pending_speech.return_value=False
        self.w._voice_capture_busy=True
        self.assertEqual(self.office._effective_state(),'LISTENING')
        self.w._voice_capture_busy=False
        self.w.command_thread=SimpleNamespace(isRunning=lambda:True)
        self.assertEqual(self.office._effective_state(),'PROCESSING')

    def test_furniture_click_mapping_after_resize_and_busy_request_preserved(self):
        from PySide6.QtCore import QPoint, Qt
        from ui.isometric_office_art import OBJECTS
        self.w.resize(1050,700);self.app.processEvents()
        emitted=[];self.office.objectActivated.connect(emitted.append)
        c=OBJECTS['sofa'][0].center()
        point=QPoint(round(self.office._scene_left+c.x()*self.office._scene_scale),
                     round(self.office._scene_top+c.y()*self.office._scene_scale))
        QTest.mouseClick(self.office,Qt.LeftButton,pos=point)
        self.assertEqual(emitted,['sofa'])
        self.assertEqual(self.office.activity,'sofa')
        self.w.neural.state='PROCESSING';self.w._active_request='filosofia'
        self.office.sync_activity()
        QTest.mouseClick(self.office,Qt.LeftButton,pos=point)
        self.assertEqual(self.office.activity,'books')
        self.assertIsNone(self.office.object_at(QPoint(0,0)))

    def test_keyboard_can_activate_furniture(self):
        from PySide6.QtCore import Qt
        QTest.keyClick(self.office,Qt.Key_Right)
        QTest.keyClick(self.office,Qt.Key_Return)
        self.assertEqual(self.office.activity,'read')

if __name__=='__main__':unittest.main()
