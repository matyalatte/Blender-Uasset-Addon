bl_info = {
    'name': 'Uasset format',
    'author': 'Matyalatte',
    'version': (0, 1, 0),
    'blender': (3, 0, 0),
    'location': 'File > Import-Export',
    'description': 'Import assets from .uasset',
    'warning': "Only works with FF7R's assets.",
    'support': 'COMMUNITY',
    'category': 'Import-Export',
}

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Operator, PropertyGroup
from bpy_extras.io_utils import ImportHelper

class TABFLAGS_WindowManager(PropertyGroup):
    ui_mesh : BoolProperty(name='Mesh', default=True)
    ui_armature : BoolProperty(name='Armature', default=True)
    ui_scale : BoolProperty(name='Scale', default=True)

class ImportUasset(Operator, ImportHelper):
    '''Load a .uasset file'''
    bl_idname = 'import.uasset'
    bl_label = 'Import Uasset'
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(default='*.uasset', options={'HIDDEN'})

    files: CollectionProperty(
        name='File Path',
        type=bpy.types.OperatorFileListElement,
    )

    

    rename_armature: BoolProperty(
        name='Rename Armature',
        description=(
            "Rename armature to 'Armature'.\n"
            "If the asset is skeleton or you check 'Keep Sections',\n"
            'this flag will be ignored'
        ),
        default=True,
    )

    shading: EnumProperty(
        name='Shading',
        items=(('SMOOTH', 'Smooth', ''),
            ('FLAT', 'Flat', '')),
        description='Apply smooth shading',
        default='SMOOTH'
    )

    keep_sections: BoolProperty(
        name='Keep Sections',
        description=(
            'Import sections as mutiple meshes.\n'
            'When off, join them into a mesh'
        ),
        default=False,
    )

    load_textures: BoolProperty(
        name='Load Textures',
        description=(
            'Load texture files if exists.\n'
            'It will take a long time'
        ),
        default=False,
    )

    minimal_bone_length : FloatProperty(
        name = 'Minimal Bone Length',
        description = 'Force all bones to be longer than this value',
        default = 0.025, min = 0.01, max = 1, step = 0.005, precision = 4,
    )

    normalize_bones: BoolProperty(
        name='Normalize Bones',
        description=(
            'Force all bones to have the double length of the "Minimal Bone Length"'
        ),
        default=True,
    )

    rotate_bones: BoolProperty(
        name='Rotate Bones',
        description=(
            'Rotate all bones by 90 degrees.\n'
            'When on, it looks better in Blender, but will not work with UE4'
        ),
        default=False,
    )

    only_skeleton: BoolProperty(
        name='Only Skeleton',
        description=(
            "Import skeleton data. but won't import mesh."
        ),
        default=False,
    )

    show_axes: BoolProperty(
        name='Show Bone Axes',
        description=(
            'Display bone axes.'
        ),
        default=False,
    )

    bone_display_type: EnumProperty(
        name='Bone Display Type',
        items=(('OCTAHEDRAL', 'Octahedral', ' Display bones as octahedral shape'),
            ('STICK', 'Stick', 'Display bones as simple 2D lines with dots'),
            ('BBONE', 'B-Bone', 'Display bones as boxes, showing subdivision and B-Splines'),
            ('ENVELOPE', 'Envelope', 'Display bones as extruded spheres, showing deformation influence volume'),
            ('WIRE', 'Wire', 'Display bones as thin wires, showing subdivision and B-Splines')
            ),
        description='Appearance of bones',
        default='STICK'
    )

    unit_scale: EnumProperty(
        name='Unit Scale',
        items=(('CENTIMETERS', 'Centimeters', 'UE standard'),
               ('METERS', 'Meters', 'Blender standard')),
        description='Change unit scale to',
        default='CENTIMETERS'
    )

    rescale : FloatProperty(
        name = 'Rescale',
        description = 'Rescale mesh and skeleton',
        default = 1, min = 0.01, max = 100, step = 0.01, precision = 3,
    )

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = False
        layout.use_property_decorate = False  # No animation.

        layout.label(text = 'Only works with FF7R.')
        layout.separator()

        wm = bpy.context.window_manager.tabflags
        row = layout.row(align = True)
        row.alignment = 'LEFT'
        row.prop(wm, 'ui_mesh', icon='TRIA_DOWN' if wm.ui_mesh else 'TRIA_RIGHT', emboss=False)
        if wm.ui_mesh:
            layout.prop(self, 'shading')
            layout.prop(self, 'keep_sections')
            layout.prop(self, 'load_textures')
            layout.separator()
        row = layout.row(align = True)
        row.alignment = 'LEFT'
        row.prop(wm, 'ui_armature', icon='TRIA_DOWN' if wm.ui_armature else 'TRIA_RIGHT', emboss=False)
        if wm.ui_armature:
            layout.prop(self, 'rotate_bones')
            layout.prop(self, 'minimal_bone_length')
            layout.prop(self, 'normalize_bones')
            layout.prop(self, 'rename_armature')
            layout.prop(self, 'only_skeleton')
            layout.prop(self, 'show_axes')
            layout.prop(self, 'bone_display_type')
            layout.separator()
        row = layout.row(align = True)
        row.alignment = 'LEFT'
        row.prop(wm, 'ui_scale', icon='TRIA_DOWN' if wm.ui_scale else 'TRIA_RIGHT', emboss=False)
        if wm.ui_scale:
            layout.prop(self, 'unit_scale')
            layout.prop(self, 'rescale')

    def invoke(self, context, event):
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        return self.import_uasset(context)

    def import_uasset(self, context):
        import os
        import_settings = self.as_keywords()

        if self.files:
            # Multiple file import
            ret = {'CANCELLED'}
            dirname = os.path.dirname(self.filepath)
            for file in self.files:
                path = os.path.join(dirname, file.name)
                if self.unit_import(path, import_settings) == {'FINISHED'}:
                    ret = {'FINISHED'}
            return ret
        else:
            # Single file import
            return self.unit_import(self.filepath, import_settings)

    def unit_import(self, file, import_settings):
        import time
        from . import bpy_util

        try:
            start_time = time.time()
            bpy_util.set_unit_scale(import_settings['unit_scale'])

            amt = bpy_util.load_uasset(file, \
                rename_armature=import_settings['rename_armature'], \
                keep_sections=import_settings['keep_sections'], \
                normalize_bones=import_settings['normalize_bones'], \
                rotate_bones=import_settings['rotate_bones'], \
                minimal_bone_length = import_settings['minimal_bone_length'], \
                rescale = import_settings['rescale'], \
                shading = import_settings['shading'], \
                only_skeleton = import_settings['only_skeleton'], \
                show_axes=import_settings['show_axes'], \
                bone_display_type=import_settings['bone_display_type'], \
                load_textures=import_settings['load_textures']
            )

            elapsed_s = '{:.2f}s'.format(time.time() - start_time)
            print('uasset import finished in ' + elapsed_s)

            return {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            return {'CANCELLED'}

def menu_func_import(self, context):
    self.layout.operator(ImportUasset.bl_idname, text='Uasset (.uasset)')

classes = (
    TABFLAGS_WindowManager,
    ImportUasset,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.WindowManager.tabflags = PointerProperty(type=TABFLAGS_WindowManager)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    del bpy.types.WindowManager.tabflags