from . import utexture, dds
if "bpy" in locals():
    import importlib
    importlib.reload(utexture)
    importlib.reload(dds)