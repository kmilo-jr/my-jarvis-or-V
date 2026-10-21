import ctypes
import unittest
from unittest.mock import Mock
from voice.gpu_priority import _set_and_verify


class GpuPriorityTests(unittest.TestCase):
    def test_success_requires_readback(self):
        def readback(handle, pointer):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int))[0] = 1
            return 0
        setter = Mock(return_value=0)
        result = _set_and_verify(setter, readback, 'worker-handle')
        self.assertTrue(result['applied'])
        setter.assert_called_once_with('worker-handle', 1)

    def test_refusal_never_claims_success(self):
        getter = Mock()
        self.assertFalse(_set_and_verify(Mock(return_value=-1), getter, 'worker')['applied'])
        getter.assert_not_called()

    def test_failed_or_mismatched_readback_is_not_success(self):
        self.assertFalse(_set_and_verify(Mock(return_value=0), Mock(return_value=-1), 'worker')['applied'])
        self.assertFalse(_set_and_verify(Mock(return_value=0), Mock(return_value=0), 'worker')['applied'])
