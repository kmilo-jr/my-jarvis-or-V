"""A cached interactive cartoon office driven only by existing UI state.

The background is rendered once. No models, files, network or scene work runs
while this widget is hidden; returning snaps to the current task.
"""
import math
import random
import re
import time
import unicodedata
from PySide6.QtCore import Qt, QTimer, QRect, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QFont, QPixmap, QPen, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget
from .isometric_office_art import OBJECTS, TARGETS, DEPTHS, background, character, furniture, tile


def activity_for(request, state):
    if state not in {'PROCESSING', 'SPEAKING', 'LISTENING'}:
        return 'rest'
    if state == 'LISTENING':
        return 'listen'
    text = unicodedata.normalize('NFKD', str(request)).encode('ascii','ignore').decode().lower()
    if re.search(r'\b(filosofi\w*|ilosofia|filosof\w*|estoic\w*|socrates|platao|aristoteles|nietzsche|estud\w*|ingles|faculdade|aprend\w*|livr\w*|explique)\b',text):
        return 'books'
    if re.search(r'\b(agenda|calendario|lembretes?|compromissos?|alarmes?)\b',text):
        return 'calendar'
    if re.search(r'\b(musicas?|spotify|radio|playlists?|cancao|cancoes)\b',text):
        return 'music'
    return 'desk'


class PixelOffice(QWidget):
    activityChanged = Signal(str)
    objectActivated = Signal(str)
    SCENE_WIDTH, SCENE_HEIGHT = 400, 400 * 2 / 3
    TARGETS = TARGETS
    IDLE_ACTIVITIES = ('read', 'sofa', 'tv', 'sleep', 'wander')
    LABELS = {'rest':'V está disponível no escritório.', 'listen':'V está ouvindo você.',
              'books':'Na estante · filosofia e estudos', 'calendar':'No calendário · agenda e lembretes',
              'music':'No rádio · música', 'desk':'Na mesa · preparando sua resposta',
              'read':'Tempo livre · lendo na biblioteca', 'sofa':'Tempo livre · descansando no sofá',
              'tv':'Tempo livre · assistindo à TV', 'sleep':'Tempo livre · cochilando',
              'wander':'Tempo livre · passeando pelo escritório'}

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.owner = window
        self._hovered_object = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400,260)
        self.setAccessibleName('Escritório cartoon do V. Use as setas e Enter para interagir com os móveis.')
        self.activity = 'rest'; self.state = 'READY'
        self._idle_activity = 'rest'; self._idle_remaining = 3.0
        self._task_activity = None; self._task_remaining = 0.0
        self._request_key = None; self._request_activity = 'desk'
        self._route = []
        self.x,self.y = self.TARGETS['rest']
        self.phase = 0.0; self.frame_count = 0
        self._pose_time = 0.0
        self.suspended = False; self._last = time.monotonic()
        self.timer = QTimer(self); self.timer.setInterval(16)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.step)
        self._background = self.make_background()
        self._scaled_background = QPixmap()
        self._scene_scale = 1.0
        self._scene_left = self._scene_top = 0.0
        self._sprites = [[character(direction,frame) for direction in range(4)] for frame in range(2)]

    @staticmethod
    def make_background():
        return background()

    def object_at(self, point):
        x=(point.x()-self._scene_left)/self._scene_scale
        y=(point.y()-self._scene_top)/self._scene_scale
        for key in sorted(OBJECTS,key=DEPTHS.get,reverse=True):
            rect,image=tile(key)
            if rect.contains(x,y):
                px=min(image.width()-1,int((x-rect.x())*3))
                py=min(image.height()-1,int((y-rect.y())*3))
                if image.pixelColor(px,py).alpha()>32:return key
        return None

    def _object_region(self,key):
        if key not in OBJECTS:return QRect()
        rect=OBJECTS[key][0].adjusted(-5,-5,5,5)
        return QRectF(self._scene_left+rect.x()*self._scene_scale,
                      self._scene_top+rect.y()*self._scene_scale,
                      rect.width()*self._scene_scale,rect.height()*self._scene_scale).toAlignedRect()

    def _set_hover(self,key):
        if key==self._hovered_object:return
        old=self._hovered_object;self._hovered_object=key
        self.setCursor(Qt.PointingHandCursor if key else Qt.ArrowCursor)
        self.setToolTip(OBJECTS[key][1] if key else '')
        self.update(self._object_region(old).united(self._object_region(key)))

    def mouseMoveEvent(self,event):
        self._set_hover(self.object_at(event.position()))
        super().mouseMoveEvent(event)

    def leaveEvent(self,event):
        self._set_hover(None);super().leaveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            key=self.object_at(event.position())
            if key:self.activate_object(key);event.accept();return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        keys=list(OBJECTS)
        if event.key() in (Qt.Key_Left,Qt.Key_Right):
            index=keys.index(self._hovered_object) if self._hovered_object in keys else -1
            self._set_hover(keys[(index+(1 if event.key()==Qt.Key_Right else -1))%len(keys)])
            event.accept();return
        if event.key() in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space) and self._hovered_object:
            self.activate_object(self._hovered_object);event.accept();return
        super().keyPressEvent(event)

    def activate_object(self,key):
        if key not in OBJECTS:return
        # Visual interaction never starts an AI request, voice or music playback.
        if self._effective_state()=='READY':
            self._task_remaining=0
            self._idle_activity={'books':'read'}.get(key,key)
            self._idle_remaining=15
            self.sync_activity()
            self.update()
        self.objectActivated.emit(key)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._cache_background()

    def _cache_background(self):
        self._scene_scale = min(self.width()/self.SCENE_WIDTH,self.height()/self.SCENE_HEIGHT)
        width = max(1,round(self.SCENE_WIDTH*self._scene_scale))
        height = max(1,round(self.SCENE_HEIGHT*self._scene_scale))
        self._scene_left=(self.width()-width)/2
        self._scene_top=(self.height()-height)/2
        self._scaled_background=QPixmap.fromImage(self._background).scaled(
            width,height,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)

    def _actor_region(self):
        # Includes the sprite, shadow, book, speech and sleep indicators.
        return QRectF(self._scene_left+(self.x-37)*self._scene_scale,
                      self._scene_top+(self.y-47)*self._scene_scale,
                      74*self._scene_scale,75*self._scene_scale).toAlignedRect()

    def _path_to(self, target):
        # Floor waypoints keep trips out of the TV, coffee table and bed.
        west, center, east = (174,131), (200,155), (262,151)
        route=[]
        if self.x < 170:
            route.append(west)
        elif self.x > 255:
            route.append(east)
        route.append(center)
        if target[0] < 170:
            route.append(west)
            if target[1] > 145: route.append((142,148))
        elif target[0] > 255:
            route.append(east)
        route.append(target)
        # Drop consecutive identical nodes, including an already reached node.
        result=[];last=(self.x,self.y)
        for point in route:
            if math.hypot(point[0]-last[0],point[1]-last[1]) > 1:
                result.append(point);last=point
        return result

    def _can_run(self):
        return self.isVisible() and not self.suspended and not self.owner.isMinimized()

    def _effective_state(self):
        """Use actual work, not a potentially stale decorative core label."""
        raw=str(getattr(self.owner.neural,'state','READY')).upper()
        # Standalone previews have no command/audio lifecycle to consult.
        if not hasattr(self.owner,'command_thread') or not hasattr(self.owner,'voice_engine'):
            if raw=='LISTENING' and getattr(self.owner,'_voice_capture_busy',True) is False:
                return 'READY'
            return raw
        thread=self.owner.command_thread
        try:
            running=thread is not None and thread.isRunning()
        except RuntimeError:  # Qt may have just deleted a finished worker.
            running=False
        if running or getattr(self.owner,'pending_commands',None):
            return 'PROCESSING'
        voice=self.owner.voice_engine
        if voice.is_speaking() or voice.has_pending_speech():
            return 'SPEAKING'
        if getattr(self.owner,'_voice_capture_busy',False):
            return 'LISTENING'
        return 'READY'

    def begin_request(self, text):
        """Receive real command starts, including replies faster than one frame."""
        self._request_key = str(text)
        self._request_activity = activity_for(text, 'PROCESSING')
        self._task_activity = self._request_activity
        self._task_remaining = 7.0 if self._can_run() else 0.0
        if self._can_run():
            self.sync_activity(); self.timer.setInterval(16); self.timer.start(); self.update()

    def _current_activity(self):
        if self.state == 'LISTENING':
            return self._task_activity if self._task_remaining > 0 else 'listen'
        if self.state in {'PROCESSING', 'SPEAKING'}:
            request = str(getattr(self.owner, '_active_request', ''))
            if request != self._request_key:
                self._request_key = request
                self._request_activity = activity_for(request, self.state)
            return self._request_activity
        if self.state == 'READY' and self._task_remaining > 0:
            return self._task_activity
        return 'rest'

    def sync_activity(self, snap=False):
        self.state=self._effective_state()
        activity=self._current_activity()
        if activity == 'rest':
            activity = self._idle_activity
        else:
            self._idle_activity = 'rest'; self._idle_remaining = 3.0
        if activity != self.activity or snap:
            self._pose_time = 0.0
            self.activity=activity
            target = self.TARGETS[activity]
            self._route = self._path_to(target)
        label = self.LABELS[activity]
        if self.state == 'READY' and self._task_remaining > 0:
            label = 'Após o pedido · ' + {'books':'consultando a estante', 'calendar':'conferindo o calendário',
                     'music':'no rádio', 'desk':'concluindo na mesa'}.get(activity, label)
        if label != getattr(self, '_last_caption', None):
            self._last_caption = label; self.activityChanged.emit(label)
        if snap:
            self.x,self.y=self.TARGETS[self.activity]; self._route=[]

    def advance_idle(self, elapsed):
        # Local decorative routine only; it never calls the command or AI engine.
        state = self._effective_state()
        if state != 'READY' or self._task_remaining > 0 or not self._can_run():
            return
        self._idle_remaining -= elapsed
        if self._idle_remaining <= 0:
            self._idle_activity = random.choice([a for a in self.IDLE_ACTIVITIES if a != self._idle_activity])
            self._idle_remaining = random.uniform(9,16)

    def set_suspended(self, value):
        self.suspended=bool(value)
        if self._can_run():
            if not self.timer.isActive():
                self.sync_activity(snap=True);self._last=time.monotonic();self.timer.start();self.update()
        else: self.timer.stop()

    def showEvent(self,event):
        super().showEvent(event)
        self.sync_activity(snap=True);self._last=time.monotonic()
        if self._can_run(): self.timer.start()

    def hideEvent(self,event):
        self.timer.stop();self._task_remaining=0;super().hideEvent(event)

    def step(self):
        if not self._can_run(): self.timer.stop();return
        now=time.monotonic();elapsed=max(0,now-self._last);dt=min(.12,elapsed);self._last=now
        self._task_remaining=max(0,self._task_remaining-min(1,elapsed))
        self.advance_idle(min(1,elapsed))
        dirty=QRegion(self._actor_region())
        previous=(self.activity,self.state)
        dirty=dirty.united(QRegion(self._object_region(self._active_object())))
        self.sync_activity(); self.phase+=min(.5,elapsed)
        tx,ty=self._route[0] if self._route else self.TARGETS[self.activity]
        distance=math.hypot(tx-self.x,ty-self.y)
        if distance>0:
            ratio=min(1,dt*58/distance);self.x+=(tx-self.x)*ratio;self.y+=(ty-self.y)*ratio
            if ratio == 1 and self._route: self._route.pop(0)
        elif self._route: self._route.pop(0)
        if self._route or distance > 1:
            self._pose_time = 0.0
        else:
            self._pose_time += min(.5,elapsed)
        # The animated screens and walk cycle run at 60 FPS. The room itself
        # remains cached and only these small regions are invalidated.
        self.timer.setInterval(16)
        self.frame_count+=1
        for rect in (self._actor_region(),self._object_region(self._active_object()),
                     self._object_region('tv'),self._object_region('desk')):
            dirty=dirty.united(QRegion(rect))
        self.update(dirty)

    def _active_object(self):
        if self._route:return None
        return {'read':'books'}.get(self.activity,self.activity)

    def paintEvent(self,event):
        if self._scaled_background.isNull(): self._cache_background()
        p=QPainter(self)
        p.fillRect(event.rect(),QColor('#10111e'))
        # Cached at widget size: normal frames only blit the damaged region.
        p.drawPixmap(round(self._scene_left),round(self._scene_top),self._scaled_background)
        p.translate(self._scene_left,self._scene_top)
        p.scale(self._scene_scale,self._scene_scale)
        p.setRenderHint(QPainter.SmoothPixmapTransform,True)
        p.setRenderHint(QPainter.Antialiasing,True)
        active=self._active_object()
        # Cached furniture layers are sorted against the resident's feet.
        order=sorted(OBJECTS,key=DEPTHS.get)
        foreground=[]
        for key in order:
            if DEPTHS[key]>self.y and key not in (active,'sleep' if self.activity=='sleep' else ''):
                foreground.append(key)
            else:
                furniture(p,key,key==active,self.phase)
        if self._hovered_object:
            p.setPen(QPen(QColor('#ffe1b3'),1.1));p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(OBJECTS[self._hovered_object][0].adjusted(-2,-2,2,2),5,5)
        tx,ty=self._route[0] if self._route else self.TARGETS[self.activity]
        walking=math.hypot(tx-self.x,ty-self.y)>1
        frame=int(self.phase*5)%2
        direction={'books':1,'read':1,'calendar':2,'music':2,'desk':2,
                   'rest':0,'listen':0,'sofa':3,'tv':3,'sleep':0,'wander':0}[self.activity]
        if walking:
            dx,dy=tx-self.x,ty-self.y
            direction=(3 if dx>0 else 1) if abs(dx)>abs(dy) else (0 if dy>0 else 2)
        elif self.state=='SPEAKING': direction=0
        p.save();p.translate(self.x,self.y)
        p.setPen(Qt.NoPen);p.setBrush(QColor(8,5,6,105))
        p.drawEllipse(QRectF(-9,-1,18,4))
        seated=not walking and self.activity in ('sofa','tv','sleep')
        if self._sprites:
            sprite=self._sprites[frame if walking else 0][direction]
            p.save()
            if seated: p.scale(1,.8+.012*math.sin(self.phase*2))
            elif not walking and self.activity in ('read','books','music'):
                p.rotate(1.2*math.sin(self.phase*1.7))
            if not walking and self.activity=='sleep': p.rotate(16)
            p.drawImage(QRectF(-23,-40-(frame*.5 if walking else 0),46,46),sprite)
            p.restore()
        else:
            p.setBrush(QColor('#a83d50'));p.drawRoundedRect(QRectF(-6,-18,12,18),4,4)
        if not walking and self.activity in ('books','read'):
            # A warm shaded book, kept local to the actor's redraw rectangle.
            p.save();p.translate(-9,-13);p.rotate(-12)
            book=QPainterPath();book.moveTo(-9,-4);book.lineTo(0,-2)
            book.lineTo(9,-4);book.lineTo(8,5);book.lineTo(0,7);book.lineTo(-8,5);book.closeSubpath()
            p.setPen(QPen(QColor('#71452e'),.7));p.setBrush(QColor('#d5b68d'));p.drawPath(book)
            p.setPen(QPen(QColor('#8b6950'),.4));p.drawLine(0,-2,0,7)
            for y in (0,2,4):p.drawLine(-6,y,-2,y+1);p.drawLine(2,y+1,6,y)
            turn=int(self._pose_time*2)%4
            p.setPen(QPen(QColor('#f3d9b3'),.8));p.drawLine(turn-2,-1,turn-2,5)
            p.restore()
        if not walking and self.activity=='sleep':
            p.setPen(QPen(QColor('#673d50'),.5));p.setBrush(QColor('#9b5969'))
            p.drawRoundedRect(QRectF(-10,-8,21,10),1,1)
            p.setPen(QColor('#d5bba5'));p.setFont(QFont('Segoe UI',5))
            p.drawText(13,-25-frame,'z')
        if not walking and self.activity in ('desk','calendar'):
            p.setPen(QPen(QColor('#ce977a'),1.3))
            p.drawLine(-6,-11-frame,-9,-13-frame)
            p.drawLine(5,-12+frame,8,-14+frame)
        if self.state=='SPEAKING':
            p.setPen(QPen(QColor('#e9c69f'),.8))
            for i in range(3):p.drawLine(14+i*2,-24,14+i*2,-26-(i+frame)%3)
        if not walking and self.activity=='music':
            p.setPen(QPen(QColor('#e0b78b'),.8))
            p.drawLine(13,-23-frame,13,-29-frame);p.drawLine(13,-29-frame,17,-28-frame)
            p.drawEllipse(QRectF(10,-24-frame,3,2))
        p.restore()
        for key in foreground:furniture(p,key,key==active,self.phase)
        p.end()
