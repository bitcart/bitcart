import multiprocessing
import ctypes.util

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"


def fixed_find_library(name):
    if name == "c":
        result = original_find_library(name)
        if result is not None:
            return result
        else:
            return "libc.so.6"
    return original_find_library(name)


original_find_library = ctypes.util.find_library
