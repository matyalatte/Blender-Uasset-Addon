from . import uasset, dds
if "bpy" in locals():
    import importlib
    if 'uasset' in locals():
        importlib.reload(uasset)
    if 'dds' in locals():
        importlib.reload(dds)
