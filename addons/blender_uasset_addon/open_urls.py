"""UI panel to open URLs."""
import bpy


class VIEW3D_PT_urls(bpy.types.Panel):
    """UI panel to open URLs."""
    bl_label = "URLs"
    bl_idname = "VIEW3D_PT_urls"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = 'Uasset'
    bl_options = {'DEFAULT_CLOSED'}

    urls = {
        'Readme': 'https://github.com/matyalatte/Blender-Uasset-Addon',
        'Getting Started': 'https://github.com/matyalatte/Blender-Uasset-Addon/wiki/Getting-Started',
        'FAQ': 'https://github.com/matyalatte/Blender-Uasset-Addon/wiki/FAQ'
    }
    icons = ['TEXT', 'INFO', 'QUESTION']

    def draw(self, context):
        """Draw UI panel to open URLs."""
        layout = self.layout
        col = layout.column()
        for (name, url), icon in zip(VIEW3D_PT_urls.urls.items(), VIEW3D_PT_urls.icons):
            ope = col.operator('wm.url_open', text=name, icon=icon)
            ope.url = url


classes = (
    VIEW3D_PT_urls,
)


def register():
    """Regist UI panel."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregist UI panel."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
