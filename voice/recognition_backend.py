"""Whisper device selection with a CPU fallback and bundled Windows CUDA DLLs."""
import os
from pathlib import Path
import sys

_dll_handles = []
_dll_paths = set()


def prepare_cuda_libraries():
    if os.name != 'nt':
        return
    directory = Path(sys.prefix) / 'Lib' / 'site-packages' / 'torch' / 'lib'
    if not (directory / 'cublas64_12.dll').is_file() or str(directory) in _dll_paths:
        return
    _dll_handles.append(os.add_dll_directory(str(directory)))
    os.environ['PATH'] = str(directory) + os.pathsep + os.environ.get('PATH', '')
    _dll_paths.add(str(directory))


def gpu_failure(exc):
    return any(term in str(exc).lower() for term in
               ('cuda', 'cublas', 'cudnn', 'out of memory', 'insufficient memory'))


def load_model(config, force_cpu=False):
    import ctranslate2
    from faster_whisper import WhisperModel
    requested = str(config.get('device', 'cpu'))
    device = 'cpu' if force_cpu else requested
    fallback = ''
    if device == 'auto':
        try:
            device = 'cuda' if ctranslate2.get_cuda_device_count() else 'cpu'
        except Exception:
            device = 'cpu'
    compute = str(config.get('compute_type', 'auto'))
    if compute == 'auto' or force_cpu:
        compute = 'int8_float16' if device == 'cuda' else 'int8'
    name = config.get('model', 'small')
    threads = int(config.get('cpu_threads', min(8, max(2, (os.cpu_count() or 4) // 2))))
    try:
        if device == 'cuda':
            prepare_cuda_libraries()
        model = WhisperModel(name, device=device, compute_type=compute, cpu_threads=threads)
    except Exception as exc:
        if device != 'cuda' or not config.get('recognition_cpu_fallback', True):
            raise
        fallback = type(exc).__name__
        device, compute = 'cpu', 'int8'
        model = WhisperModel(name, device=device, compute_type=compute, cpu_threads=threads)
    return model, {'device': device, 'compute_type': compute, 'model': name, 'fallback': fallback}
