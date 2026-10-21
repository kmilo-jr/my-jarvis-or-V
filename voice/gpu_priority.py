"""Best-effort WDDM scheduling priority for the isolated synthesis worker.

This is not a GPU utilization/VRAM cap. Never apply to the main UI process.
Microsoft: D3DKMTSetProcessSchedulingPriorityClass, BELOW_NORMAL = 1.
"""
import ctypes
import os


def _set_and_verify(setter, getter, handle):
    status = setter(handle, 1)
    if status != 0:
        return {'applied': False, 'status': f'0x{status & 0xffffffff:08x}'}
    priority = ctypes.c_int(-1)
    status = getter(handle, ctypes.byref(priority))
    return {'applied': status == 0 and priority.value == 1,
            'class': priority.value, 'status': f'0x{status & 0xffffffff:08x}'}


def lower_worker_gpu_priority():
    if os.name != 'nt':
        return {'applied': False, 'status': 'unsupported_platform'}
    try:
        dll = ctypes.WinDLL('gdi32.dll')
        setter = dll.D3DKMTSetProcessSchedulingPriorityClass
        setter.argtypes = [ctypes.c_void_p, ctypes.c_int]
        setter.restype = ctypes.c_int32
        getter = dll.D3DKMTGetProcessSchedulingPriorityClass
        getter.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        getter.restype = ctypes.c_int32
        return _set_and_verify(setter, getter, ctypes.c_void_p(-1))
    except (AttributeError, OSError):
        return {'applied': False, 'status': 'unavailable'}
