"""Blender addon to import .uasset files."""

bl_info = {
    'name': 'Uasset format',
    'author': 'Matyalatte',
    'version': (0, 2, 1),
    'blender': (2, 83, 20),
    'location': 'File > Import-Export',
    'description': 'Import assets from .uasset',
    "wiki_url": "https://github.com/matyalatte/Blender-Uasset-Addon",
    'support': 'COMMUNITY',
    'category': 'Import-Export',
}

try:
    from . import import_uasset, export_as_fbx, \
                  open_urls, inject_to_uasset, \
                  get_new_release
    from .translations import translation
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
        if "get_new_release" in locals():
            importlib.reload(get_new_release)
        if "translation" in locals():
            importlib.reload(translation)

    def register():
        """Add addon."""
        translation.register()
        get_new_release.register(bl_info['version'])
        import_uasset.register()
        inject_to_uasset.register()
        export_as_fbx.register()
        open_urls.register()

    def unregister():
        """Remove addon."""
        translation.unregister()
        get_new_release.unregister(bl_info['version'])
        import_uasset.unregister()
        inject_to_uasset.unregister()
        export_as_fbx.unregister()
        open_urls.unregister()

except ModuleNotFoundError as exc:
    print(exc)
    print('bpy not found.')
