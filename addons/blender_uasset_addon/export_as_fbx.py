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


def export_as_fbx(file, armature, meshes, global_scale=1.0, smooth_type='FACE',
                  export_tangent=False, use_custom_props=False,
                  bake_anim=True, bake_anim_use_all_bones=True,
                  bake_anim_use_nla_strips=True, bake_anim_use_all_actions=True,
                  bake_anim_force_startend_keying=True, bake_anim_step=1.0,
                  bake_anim_simplify_factor=1.0):
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
        axis_forward='-Z',
        axis_up='Y',
        bake_anim=bake_anim,
        bake_anim_use_all_bones=bake_anim_use_all_bones,
        bake_anim_use_nla_strips=bake_anim_use_nla_strips,
        bake_anim_use_all_actions=bake_anim_use_all_actions,
        bake_anim_force_startend_keying=bake_anim_force_startend_keying,
        bake_anim_step=bake_anim_step,
        bake_anim_simplify_factor=bake_anim_simplify_factor
    )

    if armature is not None:
        armature.name = armature_name
        if true_armature is not None:
            true_armature.name = 'Armature'

    bpy.ops.object.mode_set(mode=mode)


class UassetFbxOptions(bpy.types.PropertyGroup):
    """Properties for export function."""
    global_scale: FloatProperty(
            name="Scale",
            description="Scale all data (Some importers do not support scaled armatures!)",
            min=0.001, max=1000.0,
            soft_min=0.01, soft_max=1000.0,
            default=1.0,
    )
    export_tangent: BoolProperty(
        name='Export tangent',
        description="Add binormal and tangent vectors, together with normal they form the tangent space "
                    "(will only work correctly with tris/quads only meshes!)",
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
    use_custom_props: BoolProperty(
        name='Export custom properties',
        description='Export custom properties',
        default=False
    )
    show_anim_options: BoolProperty(
            name="Animation",
            default=False,
            )
    bake_anim: BoolProperty(
            name="Baked Animation",
            description="Export baked keyframe animation",
            default=False,
            )
    bake_anim_use_all_bones: BoolProperty(
            name="Key All Bones",
            description="Force exporting at least one key of animation for all bones "
                        "(needed with some target applications, like UE4)",
            default=True,
            )
    bake_anim_use_nla_strips: BoolProperty(
            name="NLA Strips",
            description="Export each non-muted NLA strip as a separated FBX's AnimStack, if any, "
                        "instead of global scene animation",
            default=True,
            )
    bake_anim_use_all_actions: BoolProperty(
            name="All Actions",
            description="Export each action as a separated FBX's AnimStack, instead of global scene animation "
                        "(note that animated objects will get all actions compatible with them, "
                        "others will get no animation at all)",
            default=True,
            )
    bake_anim_force_startend_keying: BoolProperty(
            name="Force Start/End Keying",
            description="Always add a keyframe at start and end of actions for animated channels",
            default=True,
            )
    bake_anim_step: FloatProperty(
            name="Sampling Rate",
            description="How often to evaluate animated values (in frames)",
            min=0.01, max=100.0,
            soft_min=0.1, soft_max=10.0,
            default=1.0,
            )
    bake_anim_simplify_factor: FloatProperty(
            name="Simplify",
            description="How much to simplify baked values (0.0 to disable, the higher the more simplified)",
            min=0.0, max=100.0,  # No simplification to up to 10% of current magnitude tolerance.
            soft_min=0.0, soft_max=10.0,
            default=1.0,  # default: min slope: 0.005, max frame step: 10.
            )


class UASSET_OT_export_fbx(bpy.types.Operator, ExportHelper):
    """Operator for export function."""
    bl_idname = "uasset.export_fbx"
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
        export_options = context.scene.uasset_export_options
        for key in ['global_scale', 'smooth_type', 'export_tangent', 'use_custom_props']:
            col.prop(export_options, key)
        box = layout.box()
        row = box.row(align=True)
        row.alignment = 'LEFT'
        show_flag = export_options.show_anim_options
        icon = 'DOWNARROW_HLT' if show_flag else 'RIGHTARROW'
        row.prop(export_options, 'show_anim_options', icon=icon, emboss=False)
        if show_flag:
            box.use_property_split = True
            box.use_property_decorate = False
            box.prop(export_options, 'bake_anim')
            col = box.column()
            prop_list = [
                'bake_anim_use_all_bones',
                'bake_anim_use_nla_strips',
                'bake_anim_use_all_actions',
                'bake_anim_force_startend_keying',
                'bake_anim_step',
                'bake_anim_simplify_factor'
            ]
            for prop in prop_list:
                col.prop(export_options, prop)
            col.enabled = export_options.bake_anim

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
            export_options = context.scene.uasset_export_options

            # main
            export_as_fbx(file, armature, meshes,
                          global_scale=export_options.global_scale,
                          smooth_type=export_options.smooth_type,
                          export_tangent=export_options.export_tangent,
                          use_custom_props=export_options.use_custom_props,
                          bake_anim=export_options.bake_anim,
                          bake_anim_use_all_bones=export_options.bake_anim_use_all_bones,
                          bake_anim_use_nla_strips=export_options.bake_anim_use_nla_strips,
                          bake_anim_use_all_actions=export_options.bake_anim_use_all_actions,
                          bake_anim_force_startend_keying=export_options.bake_anim_force_startend_keying,
                          bake_anim_step=export_options.bake_anim_step,
                          bake_anim_simplify_factor=export_options.bake_anim_simplify_factor)
            self.report({'INFO'}, f'Success! Saved {file}.')

        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'FINISHED'}


class UASSET_PT_export_panel(bpy.types.Panel):
    """UI panel for export function."""
    bl_space_type = 'VIEW_3D'
    bl_idname = 'UASSET_PT_export_panel'
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
        col.operator(UASSET_OT_export_fbx.bl_idname, icon='MESH_DATA')
        export_options = context.scene.uasset_export_options
        for prop in ['global_scale', 'smooth_type', 'export_tangent', 'use_custom_props']:
            col.prop(export_options, prop)


classes = (
    UassetFbxOptions,
    UASSET_OT_export_fbx,
    UASSET_PT_export_panel
)


def register():
    """Regist UI panel, operator, and properties."""
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.uasset_export_options = PointerProperty(type=UassetFbxOptions)


def unregister():
    """Unregist UI panel, operator, and properties."""
    for cls in classes:
        unregister_class(cls)

    del bpy.types.Scene.uasset_export_options
