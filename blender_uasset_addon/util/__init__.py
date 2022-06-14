import py_compile
from . import io_util
if "bpy" in locals():
    import importlib
    if "io_util" in locals():
        importlib.reload(io_util)