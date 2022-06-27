bl_info = {
    'name': 'Uasset format',
    'author': 'Matyalatte',
    'version': (0, 1, 5),
    'blender': (3, 0, 0),
    'location': 'File > Import-Export',
    'description': 'Import assets from .uasset',
    'warning': "Only works with FF7R's assets.",
    "wiki_url": "https://github.com/matyalatte/Blender-Uasset-Addon",
    'support': 'COMMUNITY',
    'category': 'Import-Export',
}

try:
    import bpy
    from . import import_uasset, export_as_fbx, open_urls, inject_to_uasset
    if "bpy" in locals():
        import importlib
        if "import_uasset" in locals():
            importlib.reload(import_uasset)
        if "inject_to_uasset" in locals():
            importlib.reload(inject_to_uasset)
        if "export_as_fbx" in locals():
            importlib.reload(export_as_fbx)
        if "open_urls" in locals():
            importlib.reload(open_urls)

    def register():
        import_uasset.register()
        inject_to_uasset.register()
        export_as_fbx.register()
        open_urls.register()

    def unregister():
        import_uasset.unregister()
        inject_to_uasset.unregister()
        export_as_fbx.unregister()
        open_urls.unregister()
except:
    print('bpy not found.')