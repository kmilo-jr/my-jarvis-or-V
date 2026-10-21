from __future__ import annotations
import os, subprocess, ctypes, webbrowser


def _key(vk:int):
    ctypes.windll.user32.keybd_event(vk,0,0,0); ctypes.windll.user32.keybd_event(vk,0,2,0)

def volume_up(): _key(0xAF)
def volume_down(): _key(0xAE)
def volume_mute(): _key(0xAD)
def media_play_pause(): _key(0xB3)
def media_next(): _key(0xB0)
def media_previous(): _key(0xB1)

def lock_pc():
    ctypes.windll.user32.LockWorkStation()

def shutdown_pc():
    subprocess.Popen(['shutdown','/s','/t','3'], creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def restart_pc():
    subprocess.Popen(['shutdown','/r','/t','3'], creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def cancel_shutdown():
    subprocess.Popen(['shutdown','/a'], creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def open_browser(): webbrowser.open('https://www.google.com')
def open_youtube(): webbrowser.open('https://www.youtube.com')
def open_spotify():
    try: os.startfile('spotify:')
    except Exception: subprocess.Popen(['cmd','/c','start','','spotify:'], shell=False)

def execute(action:str):
    fn={
      'volume_up':volume_up,'volume_down':volume_down,'volume_mute':volume_mute,
      'media_play_pause':media_play_pause,'media_next':media_next,'media_previous':media_previous,
      'lock_pc':lock_pc,'shutdown_pc':shutdown_pc,'restart_pc':restart_pc,'cancel_shutdown':cancel_shutdown,
      'open_browser':open_browser,'open_youtube':open_youtube,'open_spotify':open_spotify,
    }.get(action)
    if not fn: raise ValueError('unsupported action')
    fn()
