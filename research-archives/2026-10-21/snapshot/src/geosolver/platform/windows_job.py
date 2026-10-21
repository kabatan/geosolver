"""Windows ownership barrier: no user workload starts before Job assignment."""

import ctypes
import uuid
from ctypes import wintypes


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_processes", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _IOCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", _IOCounters),
        ("process_memory", ctypes.c_size_t),
        ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


def _kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, restype, args in (
        ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
        (
            "SetInformationJobObject",
            wintypes.BOOL,
            [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
        ),
        ("AssignProcessToJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
        (
            "IsProcessInJob",
            wintypes.BOOL,
            [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)],
        ),
        ("OpenProcess", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
        (
            "CreateEventW",
            wintypes.HANDLE,
            [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR],
        ),
        ("OpenEventW", wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]),
        ("SetEvent", wintypes.BOOL, [wintypes.HANDLE]),
        ("WaitForSingleObject", wintypes.DWORD, [wintypes.HANDLE, wintypes.DWORD]),
        ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE]),
    ):
        function = getattr(kernel, name)
        function.restype, function.argtypes = restype, args
    return kernel


class WindowsJob:
    def __init__(self):
        self.kernel = _kernel()
        self.handle = self.kernel.CreateJobObjectW(None, None)
        self.event_name = "Local\\GeoSolver-" + uuid.uuid4().hex
        self.event = self.kernel.CreateEventW(None, True, False, self.event_name)
        if not self.handle or not self.event:
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign_and_release(self, pid):
        # SET_QUOTA | TERMINATE for assignment; QUERY_INFORMATION for membership.
        process = self.kernel.OpenProcess(0x0501, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, process):
                raise ctypes.WinError(ctypes.get_last_error())
            assigned = wintypes.BOOL()
            if (
                not self.kernel.IsProcessInJob(process, self.handle, ctypes.byref(assigned))
                or not assigned.value
            ):
                raise RuntimeError("worker Job Object membership was not confirmed")
            if not self.kernel.SetEvent(self.event):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(process)

    def close(self):
        for field in ("handle", "event"):
            handle = getattr(self, field, None)
            if handle:
                self.kernel.CloseHandle(handle)
                setattr(self, field, None)


def wait_for_owner(event_name):
    kernel = _kernel()
    event = kernel.OpenEventW(0x00100000, False, event_name)
    if not event:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.WaitForSingleObject(event, 10000) != 0:
            raise TimeoutError("process owner did not establish Job membership")
    finally:
        kernel.CloseHandle(event)
