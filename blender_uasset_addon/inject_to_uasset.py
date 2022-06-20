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
import os

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
    print('Extracting mesh data from selected objects...')
    primitives = {
        'MATERIAL_IDS':[],
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
        primitives['BONES']=bone_names
        if len(bone_names) != len(armature.data.bones):
            raise RuntimeError('The number of bones are not the same. (source file: {}, blender: {})'.format(len(bone_names), len(armature.data.bones)))
    

    class BlenderMaterial:
        def __init__(self, m):
            self.import_name = m.name
            self.slot_name = None
            self.asset_path = None
            self.class_name = None

            if 'slot_name' in m:
                self.slot_name = m['slot_name']
            if 'asset_path' in m:
                self.asset_path = m['asset_path']
            if 'class' in m:
                self.class_name = m['class']

    def slots_to_materials(slots):
        return [slot.material for slot in slots]
    #get all materials
    materials = sum([slots_to_materials(mesh.material_slots) for mesh in meshes],[])
    #remove duplicated materials
    materials = list(dict.fromkeys(materials))
    material_names = [m.name for m in materials]
    primitives['MATERIALS']=[BlenderMaterial(m) for m in materials]

    rescale_factor = get_rescale_factor(rescale)
    influence_counts = []
    for mesh in meshes:
        name = mesh.name
        data_name = mesh.data.name
        splitted = bpy_util.split_mesh_by_materials(mesh)
        for m in splitted:
            primitives['MATERIAL_IDS'].append(material_names.index(m.data.materials[0].name))
            position = bpy_util.get_positions(m.data)
            position = bpy_util.flip_y_for_3d_vectors(position) * rescale_factor
            primitives['POSITIONS'].append(position.tolist())
            normal, tangent, signs = bpy_util.get_normals(m.data)
            normal = bpy_util.flip_y_for_3d_vectors(normal)
            tangent = bpy_util.flip_y_for_3d_vectors(tangent)
            zeros = np.zeros((len(m.data.loops), 1), dtype=np.float32)
            normal = np.concatenate([tangent, signs, normal, zeros], axis=1)
            vertex_indices = np.empty(len(m.data.loops), dtype=np.uint32)
            m.data.loops.foreach_get('vertex_index', vertex_indices)
            unique, indices, inverse = np.unique(vertex_indices, return_index=True, return_inverse=True)
            sort_ids = np.argsort(unique)
            normal = normal[indices][sort_ids]
            normal = ((normal + 1) * 127).astype(np.uint8)
            primitives['NORMALS'].append(normal.tolist())
            uv_maps = bpy_util.get_uv_maps(m.data)
            uv_maps = uv_maps[:, indices][:, sort_ids]
            uv_maps = bpy_util.flip_uv_maps(uv_maps)            
            if primitives['UV_MAPS']==[]:
                primitives['UV_MAPS'] = uv_maps
            else:
                primitives['UV_MAPS'] = np.concatenate([primitives['UV_MAPS'], uv_maps], axis=1)
            indices = bpy_util.get_triangle_indices(m.data)
            primitives['INDICES'].append(indices)
            if armature is not None:
                vertex_group, joint, weight, max_influence_count = bpy_util.get_weights(m, bone_names)
                influence_counts.append(max_influence_count)
                primitives['VERTEX_GROUPS'].append(vertex_group)
                primitives['JOINTS'].append(joint)
                primitives['WEIGHTS'].append(weight)
                if max_influence_count>8:
                    raise RuntimeError('Some vertices have more than 8 bone weights. UE can not handle the weight data.')

        def floor4(i):
            mod = i % 4
            return i + 4*(mod>0) - mod

        def lists_zero_fill(lists, length):
            return [l+[0]*(length-len(l)) for l in lists]
        def f_to_i(w):
            w = np.array(w, dtype=np.float32) * 255
            w = w.astype(np.uint8)
            return w.tolist()
 
        influence_count = max([floor4(i) for i in influence_counts])
        primitives['JOINTS'] = [lists_zero_fill(j, influence_count) for j in primitives['JOINTS']]
        primitives['WEIGHTS'] = [f_to_i(lists_zero_fill(w, influence_count)) for w in primitives['WEIGHTS']]
        primitives['UV_MAPS'] = primitives['UV_MAPS'].tolist()
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

            if asset_type!='SkeletalMesh':
                raise RuntimeError('Unsupported asset. ({})'.format(asset_type))
            
            primitives = get_primitives(asset, armature, meshes)

            asset.uexp.import_from_blender(primitives)

            asset.save(os.path.join(self.directory, asset.name+'.uasset'))

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

        layout.operator(InjectToUasset.bl_idname, text='Inject to Uasset (Experimantal)', icon = 'MESH_DATA')
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
