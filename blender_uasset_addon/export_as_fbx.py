"""UI panel to export objects as fbx.

Notes:
    It will use the same function as the standard fbx I/O.
    But many options are fixed to prevent user errors.
"""

import bpy
from bpy.props import BoolProperty, PointerProperty, StringProperty, FloatProperty, EnumProperty
from bpy.utils import register_class, unregister_class
from bpy_extras.io_utils import ExportHelper

from . import bpy_util
if "bpy" in locals():
    import importlib
    if "bpy_util" in locals():
        importlib.reload(bpy_util)


def export_as_fbx(file, armature, meshes, export_options):
    """Export an armature and meshed as fbx."""
    mode = bpy.context.object.mode
    bpy.ops.object.mode_set(mode='OBJECT')

    if armature is not None:
        armature_name = armature.name
        if 'Armature' in bpy.data.objects:
            true_armature = bpy.data.objects['Armature']
        else:
            true_armature = None

        if true_armature is not None:
            true_armature.name = '__temp_armature_name__'
        armature.name = 'Armature'

    # deselect all
    bpy_util.deselect_all()

    # select objects
    bpy_util.select_objects([armature] + meshes)

    global_scale = export_options.fGlobalScale
    smooth_type = export_options.smooth_type
    export_tangent = export_options.bExportTangent
    use_custom_props = export_options.bUseCustomProps

    # export as fbx
    bpy.ops.export_scene.fbx(
        filepath=file,
        use_selection=True,
        use_active_collection=False,
        global_scale=global_scale,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_NONE',
        object_types=set(['ARMATURE', 'MESH']),
        use_mesh_modifiers=True,
        mesh_smooth_type=smooth_type,
        use_tspace=export_tangent,
        use_custom_props=use_custom_props,
        add_leaf_bones=False,
        primary_bone_axis='Y',
        secondary_bone_axis='X',
        armature_nodetype='NULL',
        bake_anim=False,
        axis_forward='-Z',
        axis_up='Y'
    )

    if armature is not None:
        armature.name = armature_name
        if true_armature is not None:
            true_armature.name = 'Armature'

    bpy.ops.object.mode_set(mode=mode)


class ExportFbxOptions(bpy.types.PropertyGroup):
    """Properties for export function."""
    fGlobalScale: FloatProperty(
        name='Scale',
        description='Scale all data',
        default=1.0, min=0.01, max=100, step=0.1, precision=2,
    )
    bExportTangent: BoolProperty(
        name='Export tangent',
        description='Add binormal and tangent vectors.',
        default=False
    )
    smooth_type: EnumProperty(
        name="Smoothing",
        description='Export smoothing information.',
        items=(('OFF', 'Normals Only', 'Export only normals'),
               ('FACE', 'Face', 'Write face smoothing'),
               ('EDGE', 'Edge', 'Write edge smoothing')),
        default='FACE'
    )
    bUseCustomProps: BoolProperty(
        name='Export custom properties',
        description='Export custom properties',
        default=False
    )


class EXPORT_OT_run_button(bpy.types.Operator, ExportHelper):
    """Operator for export function."""
    bl_idname = "export_as_fbx.run_button"
    bl_label = "Export as fbx"
    bl_description = (
        'Export selected armature and meshes as fbx.\n'
        "It'll use the same export function as the default one,\n"
        "but it's customized to prevent some user errors"
    )
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = '.fbx'

    filepath: StringProperty(
        name='File Path'
    )

    def draw(self, context):
        """Draw options for file picker."""
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        export_options = context.scene.uasset_addon_fbx_export_options
        for key in ['fGlobalScale', 'smooth_type', 'bExportTangent', 'bUseCustomProps']:
            col.prop(export_options, key)

    def invoke(self, context, event):
        """Invoke."""
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        """Export selected objects to a selected file."""
        try:
            armature, meshes = bpy_util.get_selected_armature_and_meshes()
            if armature is None and meshes == []:
                raise RuntimeError('Select objects')

            file = self.filepath
            export_options = context.scene.uasset_addon_fbx_export_options

            # main
            export_as_fbx(file, armature, meshes, export_options)
            self.report({'INFO'}, f'Success! Saved {file}.')

        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'FINISHED'}


class EXPORT_PT_panel(bpy.types.Panel):
    """UI panel for export function."""
    bl_space_type = 'VIEW_3D'
    bl_idname = 'VIEW3D_PT_export_as_fbx'
    bl_region_type = 'UI'
    bl_category = "Uasset"
    bl_label = "Export as fbx"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        """Draw UI panel."""
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.operator(EXPORT_OT_run_button.bl_idname, icon='MESH_DATA')
        export_options = context.scene.uasset_addon_fbx_export_options
        for key in ['fGlobalScale', 'smooth_type', 'bExportTangent', 'bUseCustomProps']:
            col.prop(export_options, key)


classes = (
    ExportFbxOptions,
    EXPORT_PT_panel,
    EXPORT_OT_run_button
)


def register():
    """Regist UI panel, operator, and properties."""
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.uasset_addon_fbx_export_options = PointerProperty(type=ExportFbxOptions)


def unregister():
    """Unregist UI panel, operator, and properties."""
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.uasset_addon_fbx_export_options
