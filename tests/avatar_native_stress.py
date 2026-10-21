"""Exercise native avatar windows without microphones, accounts or model loading."""
import faulthandler
from pathlib import Path
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from tests.test_game_mode import Window

if __name__ == '__main__':
    Path('logs').mkdir(exist_ok=True)
    with open('logs/avatar_native_stress.log', 'w') as log:
        faulthandler.enable(log)
        app = QApplication.instance() or QApplication([])
        for cycle in range(8):
            w = Window()
            w.enqueue_command = lambda text: None
            w.toggle_continuous_voice = lambda: None
            w.show(); app.processEvents()
            game = w.game_mode
            game.minimize(); app.processEvents()
            for step in range(12):
                w.neural.state = list(game.orb.LABELS)[step % 5]
                game.orb._tick()
                QTest.mouseClick(game.orb, Qt.LeftButton)
                QTest.qWait(25)
                assert game.quick_chat.isVisible()
                game.quick_chat.input.setText('pedido de teste')
                QTest.keyClick(game.quick_chat.input, Qt.Key_Return)
                game.quick_chat.mic.click()
                game.orb.grab()
                # Exercise every animation transform, including its end frame.
                for kind in range(4):
                    game.orb._greeting_kind = kind
                    for progress in (0, .25, .5, .75, 1):
                        game.orb._greeting_frame(progress)
                        game.orb.grab()
                game.quick_chat.hide()
                if step % 3 == 0:
                    game.restore(); app.processEvents()
                    game.minimize(); app.processEvents()
            game.shutdown(); w.close(); w.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
        print('96 native click/send/hide cycles and 8 window lifecycles passed.')
