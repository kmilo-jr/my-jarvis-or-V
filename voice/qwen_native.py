"""Pinned Qwen Studio v0.2.9 C ABI; import only in the isolated worker."""
import ctypes as C
import json
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'vendor/qwen-eval'
RUNTIME = BASE / 'runtime/qwen-tts-studio'
directories = [os.add_dll_directory(str(RUNTIME)), os.add_dll_directory(str(RUNTIME / 'runtime/bin'))]
lib = C.CDLL(str(RUNTIME / 'qwen3_tts.dll'))

class Params(C.Structure):
    _fields_ = [('max_audio_tokens', C.c_int32), ('temperature', C.c_float),
                ('top_p', C.c_float), ('top_k', C.c_int32), ('n_threads', C.c_int32),
                ('print_progress', C.c_int32), ('print_timing', C.c_int32),
                ('repetition_penalty', C.c_float), ('language_id', C.c_int32),
                ('instruction', C.c_char_p), ('speaker', C.c_char_p),
                ('vocoder_left_context_sec', C.c_float)]

class Result(C.Structure):
    _fields_ = [('audio', C.POINTER(C.c_float)), ('audio_len', C.c_int32),
                ('sample_rate', C.c_int32), ('success', C.c_int32),
                ('error_msg', C.c_char_p), ('t_total_ms', C.c_int64)]

def bind(name, args, result):
    fn = getattr(lib, name)
    fn.argtypes = args
    fn.restype = result
    return fn

init = bind('qwen3_tts_init', [], C.c_void_p)
free = bind('qwen3_tts_free', [C.c_void_p], None)
load = bind('qwen3_tts_load_models_with_name', [C.c_void_p, C.c_char_p, C.c_char_p], C.c_int32)
synthesize = bind('qwen3_tts_synthesize_with_speaker_embedding', [C.c_void_p, C.c_char_p, C.c_char_p, Params], Result)
synthesize_icl = bind('qwen3_tts_synthesize_with_icl_prompt', [C.c_void_p, C.c_char_p, C.c_char_p, Params], Result)
extract = bind('qwen3_tts_extract_speaker_embedding', [C.c_void_p, C.c_char_p, C.c_char_p], C.c_int32)
free_result = bind('qwen3_tts_free_result', [Result], None)
backend = bind('qwen3_tts_get_active_backend_name', [], C.c_char_p)
error = bind('qwen3_tts_get_last_error', [C.c_void_p], C.c_void_p)
free_string = bind('qwen3_tts_free_string', [C.c_void_p], None)
CPU_THREADS = max(1, min(8, int(os.environ.get('V_QWEN_CPU_THREADS', '2'))))
DEVICE = os.environ.get('V_QWEN_DEVICE', 'auto').lower()
if DEVICE not in ('auto', 'cpu', 'cuda'):
    raise ValueError('Dispositivo Qwen inválido')
bind('qwen3_tts_set_backend_preference', [C.c_int32], C.c_int32)({'auto': 0, 'cpu': 1, 'cuda': 2}[DEVICE])
bind('qwen3_tts_set_cpu_threads', [C.c_int32], C.c_int32)(CPU_THREADS)

def last_error(ctx):
    p = error(ctx)
    if not p:
        return ''
    try:
        return C.string_at(p).decode('utf-8', errors='replace')
    finally:
        free_string(p)

