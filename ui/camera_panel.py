"""Explicit camera lifecycle with bounded, latest-frame-only background work."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import time

from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoFrame
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QCheckBox, QLineEdit, QTextEdit, QStackedWidget)

from core.vision import ObjectDetector, summarize


def to_pil(image):
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    return Image.frombytes('RGB', (rgb.width(), rgb.height()), bytes(rgb.constBits()),
                           'raw', 'RGB', rgb.bytesPerLine()).copy()


class VisionProcessor:
    """Used only by one executor thread, including lazy model initialization."""
    def __init__(self, brain):
        self.brain = brain
        self.detector = None

    def run(self, image, question):
        # Mapping/converting a camera frame can be expensive. Never do it in
        # the GUI callback; retain one frame and convert only for an analysis.
        if isinstance(image, QVideoFrame):
            image = image.toImage()
        if image.isNull():
            raise RuntimeError('Não consegui converter a imagem da câmera. Tente outra câmera ou formato.')
        image = image.scaled(960, 720, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        pil = to_pil(image)
        if question is not None:
            from integrations.vision_gemini import describe_image
            encoded = io.BytesIO()
            pil.thumbnail((960, 960))
            pil.save(encoded, format='JPEG', quality=85)
            return describe_image(self.brain, encoded.getvalue(), question), None, None
        if self.detector is None:
            self.detector = ObjectDetector()
        detections = self.detector.detect(pil)
        return summarize(detections), detections, image


def select_camera_format(formats):
    """Prefer a modest 640x480 stream at normal video rates over maximum size."""
    formats = list(formats)
    if not formats:
        return None
    modest = [f for f in formats if f.resolution().width() <= 1280
              and f.resolution().height() <= 720]
    formats = modest or formats
    def score(fmt):
        size = fmt.resolution()
        fps = fmt.maxFrameRate()
        return (fps < 24, abs(size.width() * size.height() - 640 * 480),
                abs(fps - 30))
    return min(formats, key=score)


class CameraPanel(QDialog):
    answer = Signal(str)

    def __init__(self, brain=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('V / Visão e câmera')
        self.resize(850, 700)
        self.setMinimumSize(640, 560)
        self.camera = None
        self.latest = None
        self.frame_at = 0.0
        self.frame_count = 0
        self.stats_at = time.monotonic()
        self.analysis_ms = None
        self.generation = 0
        self.future = None
        self.future_generation = -1
        self.future_spoken = False
        self.future_cloud = False
        self.has_detection = False
        self.next_detection = 0.0
        self.detect_failed = False
        self.disposed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='v-vision')
        self.processor = VisionProcessor(brain)
        self.capture = QMediaCaptureSession(self)
        self.video = QVideoWidget(self)
        self.capture.setVideoOutput(self.video)
        self.sink = self.video.videoSink()
        self.sink.videoFrameChanged.connect(self._frame)
        self.devices = QMediaDevices(self)
        self.devices.videoInputsChanged.connect(self.refresh_devices)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.setAccessibleName('Câmera selecionada')
        row.addWidget(self.selector, 1)
        self.start_button = QPushButton('Ligar câmera')
        self.start_button.clicked.connect(self.start)
        row.addWidget(self.start_button)
        self.stop_button = QPushButton('Desligar câmera')
        self.stop_button.clicked.connect(self.stop)
        self.stop_button.setEnabled(False)
        row.addWidget(self.stop_button)
        layout.addLayout(row)
        self.preview = QLabel('Câmera desligada')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(560, 315)
        self.preview.setStyleSheet('background:#06121d; color:#a8d7e7; border:1px solid #26566d;')
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.preview)
        self.preview_stack.addWidget(self.video)
        self.preview_stack.setMinimumSize(560, 315)
        layout.addWidget(self.preview_stack, 1)
        self.status = QLabel('Escolha a câmera e clique em Ligar câmera.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.performance = QLabel('Vídeo ao vivo independente da análise de objetos.')
        layout.addWidget(self.performance)
        self.local_toggle = QCheckBox('Reconhecer pessoas e objetos no PC')
        self.local_toggle.setChecked(True)
        self.local_toggle.toggled.connect(self._local_changed)
        layout.addWidget(self.local_toggle)
        self.result = QLabel('A detecção não identifica pessoas pelo nome. Pode errar ou não reconhecer um objeto.')
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.detect_button = QPushButton('Dizer o que está vendo')
        self.detect_button.clicked.connect(self.detect_once)
        layout.addWidget(self.detect_button)
        self.online_toggle = QCheckBox('Permitir enviar uma foto ao Gemini quando eu pedir uma análise')
        self.online_toggle.toggled.connect(self._online_changed)
        layout.addWidget(self.online_toggle)
        row = QHBoxLayout()
        self.question = QLineEdit()
        self.question.setPlaceholderText('Ex.: descreva o objeto que estou segurando')
        self.question.setMaxLength(1500)
        self.question.returnPressed.connect(self.describe)
        row.addWidget(self.question, 1)
        self.describe_button = QPushButton('Analisar foto com Gemini')
        self.describe_button.clicked.connect(self.describe)
        row.addWidget(self.describe_button)
        layout.addLayout(row)
        self.online_result = QTextEdit()
        self.online_result.setReadOnly(True)
        self.online_result.setAccessibleName('Descrição da foto pelo Gemini')
        self.online_result.setMaximumHeight(110)
        self.online_result.hide()
        layout.addWidget(self.online_result)
        note = QLabel('Nenhum vídeo é gravado. Fechar esta janela desliga a câmera. '
                      'A análise online usa sua chave e cota do Gemini; uma foto já enviada não pode ser recolhida.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._tick)
        self.refresh_devices()

    def refresh_devices(self):
        cameras = QMediaDevices.videoInputs()
        self.available_cameras = cameras
        selected = self.selector.currentData()
        active_id = bytes(self.camera.cameraDevice().id()) if self.camera else None
        if active_id is not None and active_id not in [bytes(d.id()) for d in cameras]:
            self.stop()
            self.status.setText('A câmera foi desconectada. Conecte novamente e clique em Ligar câmera.')
        self.selector.clear()
        for device in cameras:
            self.selector.addItem(device.description().strip(), bytes(device.id()))
        index = self.selector.findData(selected)
        if index >= 0:
            self.selector.setCurrentIndex(index)
        else:
            # Prefer a real camera over virtual phone sources when available.
            for i, device in enumerate(cameras):
                if not any(s in device.description().lower() for s in ('ivcam', 'iriun', 'virtual')):
                    self.selector.setCurrentIndex(i)
                    break
        self.start_button.setEnabled(bool(cameras) and self.camera is None)
        if not cameras:
            self.status.setText('Nenhuma câmera disponível. Conecte uma webcam e confira a permissão de câmera do Windows.')

    def start(self):
        if self.camera is not None or self.disposed:
            return
        selected = self.selector.currentData()
        device = next((d for d in self.available_cameras if bytes(d.id()) == selected), None)
        if device is None:
            self.refresh_devices()
            return
        self.generation += 1
        self.detect_failed = False
        self.has_detection = False
        self.camera = QCamera(device, self)
        camera_format = select_camera_format(device.videoFormats())
        if camera_format is not None:
            self.camera.setCameraFormat(camera_format)
        self.camera.errorOccurred.connect(self._camera_error)
        self.capture.setCamera(self.camera)
        self.selector.setEnabled(False)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.frame_at = time.monotonic()
        self.stats_at = self.frame_at
        self.frame_count = 0
        self.analysis_ms = None
        self.status.setText('Iniciando câmera…')
        self.preview_stack.setCurrentWidget(self.video)
        self.camera.start()
        self.timer.start()

    def stop(self):
        self.generation += 1
        if self.future is None:
            self.timer.stop()
        camera, self.camera = self.camera, None
        if camera is not None:
            camera.stop()
            self.capture.setCamera(None)
            camera.deleteLater()
        self.latest = None
        self.sink.setVideoFrame(QVideoFrame())
        self.preview_stack.setCurrentWidget(self.preview)
        self.preview.clear()
        self.preview.setText('Câmera desligada')
        self.result.setText('Nenhuma imagem em análise.')
        self.online_result.clear()
        self.online_result.hide()
        self.status.setText('Câmera desligada.')
        self.performance.setText('Vídeo ao vivo independente da análise de objetos.')
        self.selector.setEnabled(True)
        self.start_button.setEnabled(self.selector.count() > 0)
        self.stop_button.setEnabled(False)

    def _camera_error(self, error, message):
        if self.sender() is not None and self.sender() is not self.camera:
            return
        self.stop()
        self.status.setText('Não foi possível usar a câmera. Feche outros aplicativos que a utilizam '
                            'e confira a permissão de câmera do Windows. ' + str(message)[:180])

    def _local_changed(self):
        self.detect_failed = False
        self.generation += 1
        self.result.setText('Detecção local ativada.' if self.local_toggle.isChecked() else 'Detecção local pausada.')

    def _online_changed(self, enabled):
        if not enabled and self.future is not None and self.future_cloud:
            self.generation += 1
            self.status.setText('Resultado online dispensado. A foto já enviada não pode ser recolhida.')

    @Slot(QVideoFrame)
    def _frame(self, frame):
        if self.camera is None or not frame.isValid():
            return
        now = time.monotonic()
        # Implicitly shared frame reference: constant space, no pixel copy,
        # resizing or model inference on the GUI thread. Qt renders live video.
        self.latest = QVideoFrame(frame)
        self.frame_at = now
        self.frame_count += 1

    def _show_image(self, image):
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _submit(self, question=None, spoken=False):
        if self.camera is None or self.latest is None or time.monotonic() - self.frame_at > 2:
            if spoken:
                self.answer.emit('Ligue a câmera e aguarde a imagem antes de pedir uma análise.')
            return False
        if self.future is not None:
            if spoken:
                self.answer.emit('Já estou analisando uma imagem. Aguarde um instante e tente novamente.')
            return False
        self.future_generation = self.generation
        self.future_spoken = spoken
        self.future_cloud = question is not None
        snapshot = QVideoFrame(self.latest) if isinstance(self.latest, QVideoFrame) else self.latest.copy()
        self.future_started = time.monotonic()
        self.future = self.executor.submit(self.processor.run, snapshot, question)
        if self.future_cloud:
            self.status.setText('Enviando uma foto e aguardando o Gemini…')
        return True

    def detect_once(self):
        # Promote a fresh local detection in progress instead of queueing images.
        if self.future is not None and not self.future_cloud and self.future_generation == self.generation:
            self.future_spoken = True
            return
        self.detect_failed = False
        self._submit(spoken=True)

    def describe(self, question=None):
        if not self.online_toggle.isChecked():
            self.answer.emit('Para analisar a foto online, marque a opção de envio ao Gemini na janela da câmera.')
            return
        question = question if isinstance(question, str) and question else self.question.text().strip()
        self._submit(question or 'Descreva o que está visível nesta imagem.', spoken=True)

    def _tick(self):
        if self.disposed:
            return
        now = time.monotonic()
        if self.camera is not None and now - self.stats_at >= 1:
            fps = self.frame_count / (now - self.stats_at)
            timing = f' · última análise local: {self.analysis_ms:.0f} ms' if self.analysis_ms is not None else ''
            self.performance.setText(f'Captura: {fps:.0f} quadros/s{timing}')
            self.frame_count = 0
            self.stats_at = now
        if self.camera is not None and now - self.frame_at > 8:
            self.stop()
            self.status.setText('A câmera não está enviando imagens. Verifique a conexão e tente ligar novamente.')
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            valid = self.future_generation == self.generation and self.camera is not None
            try:
                text, detections, image = future.result()
                if valid:
                    if image is not None:
                        self.analysis_ms = (now - getattr(self, 'future_started', now)) * 1000
                        self.result.setText(text)
                        self.has_detection = True
                    else:
                        self.online_result.setPlainText(text)
                        self.online_result.show()
                    self.status.setText('Câmera ligada · análise local no PC' if image is not None else 'Análise online concluída.')
                    if self.future_spoken:
                        self.answer.emit(text)
            except Exception as exc:
                if valid:
                    self.detect_failed = not self.future_cloud
                    text = str(exc)[:350]
                    self.status.setText(text)
                    if self.future_spoken:
                        self.answer.emit(text)
            elapsed = now - getattr(self, 'future_started', now)
            # Back off on slower PCs while the native preview keeps rendering.
            game_active = bool(getattr(getattr(self.parent(), 'game_mode', None), 'enabled', False))
            self.next_detection = now + max(3.0 if game_active else .7, min(3.0, elapsed * 2))
        if (self.camera is not None and self.local_toggle.isChecked() and not self.detect_failed
                and self.future is None and now >= self.next_detection):
            self._submit()
        if self.camera is None and self.future is None:
            self.timer.stop()

    def shutdown(self):
        self.stop()
        self.disposed = True
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def done(self, result):
        # QDialog's Escape key calls reject/done without a closeEvent.
        self.stop()
        self.online_toggle.setChecked(False)
        super().done(result)

    def closeEvent(self, event):
        self.stop()
        self.online_toggle.setChecked(False)
        super().closeEvent(event)
