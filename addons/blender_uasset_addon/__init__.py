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
    def reload_package(module_dict_main):
        """Reload Scripts."""
        import importlib
        from pathlib import Path

        def reload_package_recursive(current_dir, module_dict):
            for path in current_dir.iterdir():
                if "__init__" in str(path) or path.stem not in module_dict:
                    continue
                if path.is_file() and path.suffix == ".py":
                    importlib.reload(module_dict[path.stem])
                elif path.is_dir():
                    reload_package_recursive(path, module_dict[path.stem].__dict__)

        reload_package_recursive(Path(__file__).parent, module_dict_main)

    if ".import_uasset" in locals():
        reload_package(locals())

    from . import \
        import_uasset, export_as_fbx, open_urls, \
        inject_to_uasset, get_new_release, inject_texture
    from .translations import translation

    def register():
        """Add addon."""
        translation.register()
        get_new_release.register(bl_info['version'])
        import_uasset.register()
        inject_to_uasset.register()
        export_as_fbx.register()
        inject_texture.register()
        open_urls.register()

    def unregister():
        """Remove addon."""
        translation.unregister()
        get_new_release.unregister(bl_info['version'])
        import_uasset.unregister()
        inject_to_uasset.unregister()
        export_as_fbx.unregister()
        inject_texture.unregister()
        open_urls.unregister()

except ModuleNotFoundError as exc:
    print(exc)
    print('bpy not found.')
