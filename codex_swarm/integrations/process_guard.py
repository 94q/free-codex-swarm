"""Windows kill-on-close Job Object: children die even if the UI crashes."""

from __future__ import annotations
import os


class ProcessGuard:
    def __init__(self, pid: int):
        self.handle = None
        if os.name != "nt":
            return
        import ctypes as c
        from ctypes import wintypes as w

        class BASIC(c.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", c.c_int64),
                ("PerJobUserTimeLimit", c.c_int64),
                ("LimitFlags", w.DWORD),
                ("MinimumWorkingSetSize", c.c_size_t),
                ("MaximumWorkingSetSize", c.c_size_t),
                ("ActiveProcessLimit", w.DWORD),
                ("Affinity", c.c_size_t),
                ("PriorityClass", w.DWORD),
                ("SchedulingClass", w.DWORD),
            ]

        class IO(c.Structure):
            _fields_ = [
                (name, c.c_uint64)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class EXT(c.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC),
                ("IoInfo", IO),
                ("ProcessMemoryLimit", c.c_size_t),
                ("JobMemoryLimit", c.c_size_t),
                ("PeakProcessMemoryUsed", c.c_size_t),
                ("PeakJobMemoryUsed", c.c_size_t),
            ]

        k = c.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        k.SetInformationJobObject.restype = w.BOOL
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        k.OpenProcess.restype = w.HANDLE
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        k.AssignProcessToJobObject.restype = w.BOOL
        k.CloseHandle.argtypes = [w.HANDLE]
        k.CloseHandle.restype = w.BOOL
        self.kernel = k
        job = k.CreateJobObjectW(None, None)
        if not job:
            raise OSError(c.get_last_error(), "Cannot create process containment job")
        info = EXT()
        info.BasicLimitInformation.LimitFlags = 0x2000
        if not k.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info)):
            k.CloseHandle(job)
            raise OSError(c.get_last_error(), "Cannot set process containment limits")
        process = k.OpenProcess(0x0100 | 0x0001, False, pid)
        try:
            if not process or not k.AssignProcessToJobObject(job, process):
                k.CloseHandle(job)
                raise OSError(
                    c.get_last_error(),
                    "Cannot contain Codex process; execution refused",
                )
        finally:
            if process:
                k.CloseHandle(process)
        self.handle = job

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        self.close()
