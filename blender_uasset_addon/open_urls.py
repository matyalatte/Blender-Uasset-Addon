import bpy


class VIEW3D_PT_urls(bpy.types.Panel):
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
        layout = self.layout
        col = layout.column()
        for (name, url), icon in zip(VIEW3D_PT_urls.urls.items(), VIEW3D_PT_urls.icons):
            op = col.operator('wm.url_open', text=name, icon=icon)
            op.url = url


classes = (
    VIEW3D_PT_urls,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
