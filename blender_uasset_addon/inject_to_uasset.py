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

def get_bones(armature, rescale=1.0):
    bpy.context.view_layer.objects.active=armature
    bpy.ops.object.mode_set(mode='EDIT')
    rescale_factor = get_rescale_factor(rescale)
    class BlenderBone:
        def __init__(self, name, parent, matrix, index):
            self.name = name
            self.global_matrix = matrix
            if parent is None:
                self.parent_name = 'None'
                loc, rot, scale = self.global_matrix.decompose()
            else:
                self.parent_name = parent.name
                self.local_matrix = parent.matrix.inverted() @ matrix
                loc, rot, scale = self.local_matrix.decompose()
            loc = loc * rescale_factor
            self.trans = [loc[0], -loc[1], loc[2]]
            self.rot = [rot[1], -rot[2], rot[3], -rot[0]]
            self.scale = [scale[0], scale[1], scale[2]]
            self.index=index

    edit_bones = armature.data.edit_bones
    edit_bones = [BlenderBone(b.name, b.parent, b.matrix, i) for i, b in zip(range(len(edit_bones)), edit_bones)]

    bone_names = [b.name for b in edit_bones]

    def set_parent(bone, bone_names, edit_bones):
        if bone.parent_name=='None':
            bone.parent=None
        else:
            bone.parent = edit_bones[bone_names.index(bone.parent_name)]

    list(map(lambda x: set_parent(x, bone_names, edit_bones), edit_bones))

    bpy_util.move_to_object_mode()
    return edit_bones, bone_names

def get_primitives(asset, armature, meshes, rescale = 1.0, only_mesh=False):
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
        bones, bone_names = get_bones(armature, rescale=rescale)
        primitives['BONES']=bones
        primitives['BONE_NAMES']=bone_names
    
    if meshes==[]:
        return primitives

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
    if armature is not None:
        primitives['VERTEX_GROUPS']=[]
        primitives['JOINTS']=[]
        primitives['WEIGHTS']=[]
        if only_mesh:
            asset_bone_names = [b.name for b in asset.uexp.skeleton.bones]
            for n in bone_names:
                if n not in asset_bone_names:
                    raise RuntimeError("Skeletons should be same when using 'Only Mesh' option")
            bone_names = asset_bone_names
    t=0
    import time
    for mesh in meshes:
        name = mesh.name
        data_name = mesh.data.name
        try:
            mesh.data.calc_tangents()
        except:
            raise RuntimeError('Failed to calculate tangents. Meshes should be triangulated.')
        splitted = bpy_util.split_mesh_by_materials(mesh)
        err=False
        for m in splitted:
            try:
                m.data.calc_tangents()
            except:
                err=True
                break
            primitives['MATERIAL_IDS'].append(material_names.index(m.data.materials[0].name))
            position = bpy_util.get_positions(m.data)
            position = bpy_util.flip_y_for_3d_vectors(position) * rescale_factor
            primitives['POSITIONS'].append(position)

            normal, tangent, signs = bpy_util.get_normals(m.data)
            normal = bpy_util.flip_y_for_3d_vectors(normal)
            tangent = bpy_util.flip_y_for_3d_vectors(tangent)
            zeros = np.zeros((len(m.data.loops), 1), dtype=np.float32)
            normal = np.concatenate([tangent, signs, normal, zeros], axis=1)

            vertex_indices = np.empty(len(m.data.loops), dtype=np.uint32)
            m.data.loops.foreach_get('vertex_index', vertex_indices)
            unique, indices = np.unique(vertex_indices, return_index=True)
            sort_ids = np.argsort(unique)
            normal = normal[indices][sort_ids]
            normal = ((normal + 1) * 127).astype(np.uint8)
            primitives['NORMALS'].append(normal)
            uv_maps = bpy_util.get_uv_maps(m.data)
            uv_maps = uv_maps[:, indices][:, sort_ids]
            uv_maps = bpy_util.flip_uv_maps(uv_maps)            
            primitives['UV_MAPS'].append(uv_maps)
            indices = bpy_util.get_triangle_indices(m.data)
            primitives['INDICES'].append(indices)
            if armature is not None:
                st = time.time()
                vertex_group, joint, weight, max_influence_count = bpy_util.get_weights(m, bone_names)
                t += time.time() - st
                influence_counts.append(max_influence_count)
                primitives['VERTEX_GROUPS'].append(vertex_group)
                primitives['JOINTS'].append(joint)
                primitives['WEIGHTS'].append(weight)
                if max_influence_count>8:
                    raise RuntimeError('Some vertices have more than 8 bone weights. UE can not handle the weight data.')

        elapsed_s = '{:.2f}s'.format(t)
        #print('weight calculation in '+elapsed_s)
        joined = bpy_util.join_meshes(splitted)
        joined.name=name
        joined.data.name=data_name
        if err:
            raise RuntimeError('Failed to calculate tangents. Meshes should be triangulated.')
    
    primitives['VERTEX_COUNTS'] = [len(p) for p in primitives['POSITIONS']]
    for axis, key in zip([0,0,1], ['POSITIONS', 'NORMALS', 'UV_MAPS']):
        primitives[key] = np.concatenate(primitives[key], axis=axis).tolist()

    if armature is not None:
        def floor4(i):
            mod = i % 4
            return i + 4*(mod>0) - mod

        def lists_zero_fill(lists, length):
            return [l+[0]*(length-len(l)) for l in lists]

        def f_to_i(w):
            w = np.array(w, dtype=np.float32) * 255.0
            w = np.rint(w).astype(np.uint8)
            return w

        influence_count = floor4(max(influence_counts))
        primitives['JOINTS'] = [np.array(lists_zero_fill(j, influence_count), dtype=np.uint8) for j in primitives['JOINTS']]
        primitives['JOINTS'] = np.concatenate(primitives['JOINTS'], axis=0).tolist()
        primitives['WEIGHTS'] = [f_to_i(lists_zero_fill(w, influence_count)) for w in primitives['WEIGHTS']]
        primitives['WEIGHTS'] = np.concatenate(primitives['WEIGHTS'], axis=0).tolist()
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

    duplicate_folder_structure: BoolProperty(
        name='Duplicate Folder Structure',
        description=(
            'Duplicate the folder structure .uasset have'
        ),
        default=False,
    )

    content_folder: StringProperty(
        name='Content Folder',
        description=(
            'Replace the root directory of asset paths with this value\n'
            'when duplicating the folder structure'
        ),
        default='End\\Content',
    )

    mod_name: StringProperty(
        name='Mod Name',
        description=(
            'Add this value to asset paths as a root folder\n'
            'when duplicating the folder structure'
        ),
        default='mod_name_here',
    )

    rescale : FloatProperty(
        name = 'Rescale',
        description = 'Rescale mesh and skeleton',
        default = 1, min = 0.01, max = 100, step = 0.01, precision = 2,
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
        props = ['only_mesh', 'duplicate_folder_structure', 'content_folder', 'mod_name', 'rescale']
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
            #get selected objects
            armature, meshes = bpy_util.get_selected_armature_and_meshes()

            #check uv count
            uv_counts = [len(mesh.data.uv_layers) for mesh in meshes]
            if len(list(set(uv_counts)))>1:
                raise RuntimeError('All meshes should have the same number of uv maps')

            #load source file
            general_options = context.scene.general_options
            inject_options = context.scene.inject_options
            version = general_options.ue_version
            if version not in ['ff7r', '4.18']:
                raise RuntimeError('Injection is unsupported for {}'.format())
            asset = unreal.uasset.Uasset(general_options.source_file, version=version)
            asset_type = asset.asset_type

            if armature is None and 'Skelet' in asset_type:
                raise RuntimeError('Select an armature.')
            if meshes==[] and 'Mesh' in asset_type:
                raise RuntimeError('Select meshes.')
            if 'Mesh' not in asset_type and asset_type!='Skeleton':
                raise RuntimeError('Unsupported asset. ({})'.format(asset_type))

            if asset_type=='Skeleton':
                meshes=[]

            primitives = get_primitives(asset, armature, meshes, rescale=inject_options.rescale, only_mesh=inject_options.only_mesh)
            bpy_util.deselect_all()
            bpy_util.select_objects([armature]+meshes)

            print('Editing asset data...')
            asset.uexp.import_from_blender(primitives, only_mesh=inject_options.only_mesh)
            if inject_options.duplicate_folder_structure:
                dirs = asset.asset_path.split('/')
                if dirs[0]=='':
                    dirs = dirs[2:]
                else:
                    dirs = dirs[1:]
                dirs = '\\'.join(dirs)
                asset_path = os.path.join(self.directory, inject_options.mod_name, inject_options.content_folder, dirs)
            else:
                asset_path = os.path.join(self.directory, asset.name)

            asset.save(asset_path+'.uasset')

            elapsed_s = '{:.2f}s'.format(time.time() - start_time)
            m = 'Success! Injected {} in {}'.format(asset_type, elapsed_s)
            print(m)
            self.report({'INFO'}, m)
            ret = {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret

class SelectUasset(Operator):
    bl_idname = 'select.uasset'
    bl_label = 'Select Uasset'
    bl_description = 'Select .uasset file you want to mod'

    filter_glob: StringProperty(default='*.uasset', options={'HIDDEN'})

    filepath: StringProperty(
        name='File Path'
    )

    def draw(self, context):
        pass

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):

        context.scene.general_options.source_file = self.filepath
        return {'FINISHED'}

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
        layout.operator(SelectUasset.bl_idname, text='Select Source File', icon = 'FILE')
        
classes = (
    InjectOptions,
    InjectToUasset,
    SelectUasset,
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
