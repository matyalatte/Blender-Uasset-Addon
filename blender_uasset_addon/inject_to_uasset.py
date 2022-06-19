import bpy
from mathutils import Vector, Quaternion, Matrix
import numpy as np
from bpy.props import (StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Operator, PropertyGroup

from . import bpy_util, unreal, util
if "bpy" in locals():
    import importlib
    if "bpy_util" in locals():
        importlib.reload(bpy_util)
    if "unreal" in locals():
        importlib.reload(unreal)
    if "util" in locals():
        importlib.reload(util)

def get_rescale_factor(rescale):
    return bpy.context.scene.unit_settings.scale_length * 100 * rescale

def get_primitives(asset, armature, meshes, rescale = 1.0):
    primitives = {
        'POSITIONS': [],
        'NORMALS': [],
        'TANGENTS': [],
        'UV_MAPS': [],
        'INDICES': []
    }
    if armature is not None:
        primitives['VERTEX_GROUPS']=[]
        primitives['JOINTS']=[]
        primitives['WEIGHTS']=[]
        bone_names = [b.name for b in asset.uexp.skeleton.bones]
        if len(bone_names) != len(armature.data.bones):
            raise RuntimeError('The number of bones are not the same. (source file: {}, blender: {})'.format(len(bone_names), len(armature.data.bones)))
        
    rescale_factor = get_rescale_factor(rescale)
    for mesh in meshes:
        name = mesh.name
        data_name = mesh.data.name
        splitted = bpy_util.split_mesh_by_materials(mesh)
        for m in splitted:
            position = bpy_util.get_positions(m.data)
            position = bpy_util.flip_y_for_3d_vectors(position) * rescale_factor
            primitives['POSITIONS'].append(position.tolist())
            normal, tangent, signs = bpy_util.get_normals(m.data)
            normal = bpy_util.flip_y_for_3d_vectors(normal)
            tangent = bpy_util.flip_y_for_3d_vectors(tangent)
            zeros = np.zeros((len(m.data.loops), 1), dtype=np.float32)
            normal = np.concatenate([normal, zeros, tangent, signs], axis=1)
            normal = ((normal + 1) * 127).astype(np.uint8)
            primitives['NORMALS'].append(normal.tolist())
            uv_maps = bpy_util.get_uv_maps(m.data)
            uv_maps = bpy_util.flip_uv_maps(uv_maps)
            primitives['UV_MAPS'].append(uv_maps)
            indices = bpy_util.get_triangle_indices(m.data)
            primitives['INDICES'].append(indices)
            if armature is not None:
                vertex_group, joint, weight, max_influence_count = bpy_util.get_weights(m.data, bone_names)
                primitives['VERTEX_GROUPS'].append(vertex_group)
                primitives['JOINTS'].append(joint)
                primitives['WEIGHTS'].append(weight)
                if max_influence_count>8:
                    raise RuntimeError('Some vertices have more than 8 bone weights. UE can not handle the weight data.')
        joined = bpy_util.join_meshes(splitted)
        joined.name=name
        joined.data.name=data_name
    return primitives

class InjectOptions(PropertyGroup):
    only_mesh: BoolProperty(
        name='Only Mesh',
        description=(
            "Won't update skeleton data.\n"
            "It'll prevent user errors if you didn't edit the skeleton"
        ),
        default=True,
    )
    auto_rescaling: BoolProperty(
        name='Auto Rescaling',
        description=(
            'Execute m to cm (or cm to m) conversion\n'
            'if the size is more than 10 times as big (or small) as the source asset'
        ),
        default=True,
    )

class InjectToUasset(Operator):
    bl_idname = 'inject.uasset'
    bl_label = 'Export .uasset here'
    bl_description = 'Inject a selected asset to .uasset file'
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name="target_dir",
        default=''
    )

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = False
        layout.use_property_decorate = False  # No animation.

        props = ['ue_version', 'source_file']
        general_options = context.scene.general_options
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        for prop in props:
            col.prop(general_options, prop)
        inject_options = context.scene.inject_options
        props = ['only_mesh', 'auto_rescaling']
        for prop in props:
            col.prop(inject_options, prop)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import time
        start_time = time.time()
        general_options = context.scene.general_options
        if bpy_util.os_is_windows():
            bpy.ops.wm.console_toggle()
            bpy.ops.wm.console_toggle()
        try:
            print(self.directory)
            #get selected objects
            armature, meshes = bpy_util.get_selected_armature_and_meshes()

            #check uv count
            uv_counts = [len(mesh.data.uv_layers) for mesh in meshes]
            if len(list(set(uv_counts)))>1:
                raise RuntimeError('All meshes should have the same number of uv maps')

            #load source file
            general_options = context.scene.general_options
            asset = unreal.uasset.Uasset(general_options.source_file, version=general_options.ue_version)
            asset_type = asset.asset_type
            if 'Mesh' not in asset_type:
                raise RuntimeError('Unsupported asset. ({})'.format(asset_type))
            
            primitives = get_primitives(asset, armature, meshes)

            elapsed_s = '{:.2f}s'.format(time.time() - start_time)
            self.report({'ERROR'}, 'Injection is unsupported yet.')
            #self.report({'INFO'}, self.directory)
            ret = {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret

class UASSET_PT_inject_panel(bpy.types.Panel):
    bl_label = "Inject to Uasset"
    bl_idname = 'VIEW3D_PT_inject_uasset'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uasset"

    def draw(self, context):
        layout = self.layout
        
        #import_uasset.py->GeneralOptions
        general_options = context.scene.general_options

        layout.label(text = 'Injection is unsupported yet.')
        layout.label(text = "Don't use this panel.")
        layout.operator(InjectToUasset.bl_idname, text='Inject to Uasset', icon = 'MESH_DATA')
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(general_options, 'ue_version')
        col.prop(general_options, 'source_file')
        
classes = (
    InjectOptions,
    InjectToUasset,
    UASSET_PT_inject_panel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.inject_options = PointerProperty(type=InjectOptions)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.inject_options
