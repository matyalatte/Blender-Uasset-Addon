"""UI panel to inject objects into .uasset files."""
import os
import time

import bpy
import numpy as np
from bpy.props import (StringProperty,
                       BoolProperty,
                       FloatProperty,
                       PointerProperty)
from bpy.types import Operator, PropertyGroup
from mathutils import Vector, Quaternion, Euler

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
    """Calculate rescale factor from rescale value and unit scale."""
    return bpy.context.scene.unit_settings.scale_length * 100 * rescale


def get_bones(armature, rescale=1.0):
    """Extract bone data from an armature.

    Args:
        armature (bpy.types.Armature): target armature
        rescale (float): rescale factor for bone positions

    Returns:
        blender_bones (list[BlenderBone]): bone data contains name, parent, trs, etc.
        bone_names (list[string]): bone names (same as [b.name for b in blender_bones])
    """
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    rescale_factor = get_rescale_factor(rescale)

    class BlenderBone:
        """Class to store Blender's bone data."""
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
            self.index = index

    edit_bones = armature.data.edit_bones

    def get_blender_bone(bone, i):
        return BlenderBone(bone.name, bone.parent, bone.matrix, i)

    blender_bones = [get_blender_bone(b, i) for i, b in zip(range(len(edit_bones)), edit_bones)]

    bone_names = [b.name for b in blender_bones]

    def set_parent(bone, bone_names, blender_bones):
        if bone.parent_name == 'None':
            bone.parent = None
        else:
            bone.parent = blender_bones[bone_names.index(bone.parent_name)]

    list(map(lambda x: set_parent(x, bone_names, blender_bones), blender_bones))

    bpy_util.move_to_object_mode()
    return blender_bones, bone_names


def get_primitives(asset, armature, meshes, rescale=1.0, only_mesh=False):
    """Get mesh data as a dictionary.

    Args:
        asset (unreal.uasset.Uasset): traget asset
        armature (bpy.types.Armature): source armature
        meshes (list[bpy.types.Mesh]): source meshes
        rescale (float): rescale factor for objects
        only_mesh (bool): won't extract armature data

    Returns:
        primitives (dict): object data

    Notes:
        Keys for primitives.
        - BONES (list[BlenderBone])
        - BONE_NAMES (list[string])
        - MATERIALS (list[BlenderMaterial])
        - MATERIAL_IDS (list[int]): (section_count)
        - POSITIONS (list[ilst[float]]): (vertex_count, 3)
        - NORMALS (list[float]): (vertex_count, 8)
        - UV_MAPS (list[[list[float]]): (uv_count, vertex_count, 2)
        - INDICES (list[int]): (section_count, face_count*3)
        - VERTEX_GROUPS (list[list[int]]): (section_count, -1)
        - JOINTS (list[list[int]]): (vertex_count, max_influence_count)
        - WEIGHTS (list[list[int]]): (vertex_count, max_influence_count)
        - VERTEX_COUNTS (list[int]): (section_count)
    """
    print('Extracting mesh data from selected objects...')
    primitives = {
        'MATERIAL_IDS': [],
        'POSITIONS': [],
        'NORMALS': [],
        'TANGENTS': [],
        'UV_MAPS': [],
        'INDICES': []
    }
    if armature is not None:
        bones, bone_names = get_bones(armature, rescale=rescale)
        primitives['BONES'] = bones
        primitives['BONE_NAMES'] = bone_names

    if meshes == []:
        return primitives

    class BlenderMaterial:
        """Class to store Blender's material data."""
        def __init__(self, m):
            self.import_name = m.name
            self.slot_name = f'slot_{m.name}'
            self.asset_path = f'/Game/GameContents/path_to_{m.name}'
            self.class_name = None

            if 'slot_name' in m:
                self.slot_name = m['slot_name']
            if 'asset_path' in m:
                self.asset_path = m['asset_path']
            if 'class' in m:
                self.class_name = m['class']

    def slots_to_materials(slots):
        return [slot.material for slot in slots]

    # get all materials
    materials = sum([slots_to_materials(mesh.material_slots) for mesh in meshes], [])

    # remove duplicated materials
    materials = list(dict.fromkeys(materials))
    material_names = [m.name for m in materials]
    primitives['MATERIALS'] = [BlenderMaterial(m) for m in materials]

    rescale_factor = get_rescale_factor(rescale)
    influence_counts = []
    if armature is not None:
        primitives['VERTEX_GROUPS'] = []
        primitives['JOINTS'] = []
        primitives['WEIGHTS'] = []
        if only_mesh:
            asset_bone_names = [b.name for b in asset.uexp.skeleton.bones]
            for name in bone_names:
                if name not in asset_bone_names:
                    raise RuntimeError("Skeletons should be same when using 'Only Mesh' option")
            bone_names = asset_bone_names
    time_for_weights = 0
    for mesh in meshes:
        name = mesh.name
        data_name = mesh.data.name
        try:
            mesh.data.calc_tangents()
        except Exception as exc:
            raise RuntimeError('Failed to calculate tangents. Meshes should be triangulated.') from exc
        splitted = bpy_util.split_mesh_by_materials(mesh)
        err = False
        for mat in splitted:
            try:
                mat.data.calc_tangents()
            except Exception:
                err = True
                break
            primitives['MATERIAL_IDS'].append(material_names.index(mat.data.materials[0].name))
            position = bpy_util.get_positions(mat.data)
            position = bpy_util.flip_y_for_3d_vectors(position) * rescale_factor
            primitives['POSITIONS'].append(position)

            normal, tangent, signs = bpy_util.get_normals(mat.data)
            normal = bpy_util.flip_y_for_3d_vectors(normal)
            tangent = bpy_util.flip_y_for_3d_vectors(tangent)
            zeros = np.zeros((len(mat.data.loops), 1), dtype=np.float32)
            normal = np.concatenate([tangent, signs, normal, zeros], axis=1)

            vertex_indices = np.empty(len(mat.data.loops), dtype=np.uint32)
            mat.data.loops.foreach_get('vertex_index', vertex_indices)
            unique, indices = np.unique(vertex_indices, return_index=True)
            sort_ids = np.argsort(unique)
            normal = normal[indices][sort_ids]
            normal = ((normal + 1) * 127).astype(np.uint8)
            primitives['NORMALS'].append(normal)
            uv_maps = bpy_util.get_uv_maps(mat.data)
            uv_maps = uv_maps[:, indices][:, sort_ids]
            uv_maps = bpy_util.flip_uv_maps(uv_maps)
            primitives['UV_MAPS'].append(uv_maps)
            indices = bpy_util.get_triangle_indices(mat.data)
            primitives['INDICES'].append(indices)
            if armature is not None:
                start = time.time()
                vertex_group, joint, weight, max_influence_count = \
                    bpy_util.get_weights(mat, bone_names)
                time_for_weights += time.time() - start
                influence_counts.append(max_influence_count)
                primitives['VERTEX_GROUPS'].append(vertex_group)
                primitives['JOINTS'].append(joint)
                primitives['WEIGHTS'].append(weight)
                if max_influence_count > 8:
                    msg = ('Some vertices have more than 8 bone weights.'
                           'UE can not handle the weight data.')
                    raise RuntimeError(msg)

        # elapsed_s = '{:.2f}s'.format(time_for_weights)
        # print('weight calculation in '+elapsed_s)
        joined = bpy_util.join_meshes(splitted)
        joined.name = name
        joined.data.name = data_name
        if err:
            raise RuntimeError('Failed to calculate tangents. Meshes should be triangulated.')

    primitives['VERTEX_COUNTS'] = [len(p) for p in primitives['POSITIONS']]
    for axis, key in zip([0, 0, 1], ['POSITIONS', 'NORMALS', 'UV_MAPS']):
        primitives[key] = np.concatenate(primitives[key], axis=axis).tolist()

    if armature is not None:
        def floor4(i):
            mod = i % 4
            return i + 4 * (mod > 0) - mod

        def lists_zero_fill(lists, length):
            return [sub_list + [0] * (length - len(sub_list)) for sub_list in lists]

        def f_to_i(weight):
            weight = np.array(weight, dtype=np.float32) * 255.0
            weight = np.rint(weight).astype(np.uint8)
            return weight

        influence_count = floor4(max(influence_counts))
        primitives['JOINTS'] = [lists_zero_fill(j, influence_count) for j in primitives['JOINTS']]
        primitives['JOINTS'] = [np.array(j, dtype=np.uint8) for j in primitives['JOINTS']]
        primitives['JOINTS'] = np.concatenate(primitives['JOINTS'], axis=0).tolist()
        primitives['WEIGHTS'] = [lists_zero_fill(w, influence_count) for w in primitives['WEIGHTS']]
        primitives['WEIGHTS'] = [f_to_i(w) for w in primitives['WEIGHTS']]
        primitives['WEIGHTS'] = np.concatenate(primitives['WEIGHTS'], axis=0).tolist()
    return primitives


def inject_animation(asset, armature, ue_version, rescale=1.0):
    """Inject animation data into the asset."""
    anim = asset.uexp.anim

    # Get skeleton asset
    anim_path = anim.get_animation_path()
    skel_path = anim.get_skeleton_path()
    skel_basename = os.path.basename(skel_path)
    skel_search_paths = [skel_path, anim_path]
    if 'actual_path' in armature:
        skel_search_paths.append(armature['actual_path'])
    skel_path = None
    for path in skel_search_paths:
        path = os.path.join(os.path.dirname(path), skel_basename)
        if os.path.exists(path):
            skel_path = path
            print(f'Skeleton asset found ({path})')
            break
        print(f'Skeleton asset NOT found ({path})')
    if skel_path is None:
        raise RuntimeError('Skeleton asset not found.')
    bones = unreal.uasset.Uasset(skel_path, version=ue_version).uexp.skeleton.bones

    if ue_version != 'ff7r':
        raise RuntimeError(f'Animations are unsupported for this verison. ({ue_version})')

    # Get animation data
    bone_ids = anim.bone_ids
    compressed_clip = anim.compressed_data
    num_samples = compressed_clip.clip_header.num_samples
    print(f'frame count: {num_samples}')

    scene_fps = bpy_util.get_fps()
    asset_fps = compressed_clip.clip_header.sample_rate
    interval = scene_fps / asset_fps
    start_frame = 1
    print(f'injected frames: {start_frame} ~ {start_frame + num_samples * interval}')
    anim_data = bpy_util.get_animation_data(armature, start_frame=start_frame,
                                            num_samples=num_samples, interval=interval)
    bone_names = [b.name for b in bones]
    ignored_bones = [k for k in anim_data.keys() if k not in bone_names]
    if len(ignored_bones) > 0:
        print(f'Ignored some bones does NOT exist in the animation asset. ({ignored_bones})')

    class BlenderBoneTrack:
        """Animation tracks for a bone."""
        def __init__(self):
            self.rot = []
            self.trans = []
            self.scale = []

    def vec_add(a, b):
        return [a_ + b_ for a_, b_ in zip(a, b)]

    def vec_mult(a, b):
        return [a_ * b_ for a_, b_ in zip(a, b)]

    rescale_factor = get_rescale_factor(rescale)
    bone_tracks = [BlenderBoneTrack() for i in range(len(bone_ids))]
    for idx, track in zip(bone_ids, bone_tracks):
        bone = bones[idx]
        if bone.name not in anim_data:
            continue
        bone_anim_data = anim_data[bone.name]
        for data_type, elem_anim_data in bone_anim_data.items():
            if len(elem_anim_data) == 0:
                continue
            if 'rotation' in data_type:
                for vec in elem_anim_data:
                    if 'quaternion' in data_type:
                        quat_diff = Quaternion(vec).normalized()
                    else:
                        euler = Euler(vec)
                        quat_diff = euler.to_quaternion(euler)
                    quat = bone.rot
                    default_quat = Quaternion([-quat[3], quat[0], -quat[1], quat[2]])
                    new_quat = default_quat @ quat_diff
                    new_quat_dropw = [new_quat[1], -new_quat[2], new_quat[3]]
                    if new_quat[0] > 0:
                        new_quat_dropw = [-x for x in new_quat_dropw]
                    track.rot.append(new_quat_dropw)
            elif data_type == 'location':
                for vec in elem_anim_data:
                    trans_diff = Vector(vec)
                    quat = bone.rot
                    default_quat = Quaternion([-quat[3], quat[0], -quat[1], quat[2]])
                    trans_diff *= rescale_factor
                    trans_diff = default_quat @ trans_diff
                    trans_diff[1] *= -1
                    trans = vec_add(trans_diff, bone.trans)
                    track.trans.append(trans)
            elif data_type == 'scale':
                for vec in elem_anim_data:
                    track.scale.append(vec_mult(vec, bone.scale))
    anim.import_anim_data(bone_tracks)


def inject_uasset(source_file, directory, ue_version='4.18',
                  rescale=1.0, only_mesh=True,
                  duplicate_folder_structure=True,
                  mod_name='mod_name_here',
                  content_folder='End\\Content'):
    """Inject selected objects to uasset file."""
    # load source file
    version = ue_version
    if version not in ['ff7r', '4.18']:
        raise RuntimeError(f'Injection is unsupported for {version}')
    asset = unreal.uasset.Uasset(source_file, version=version)
    asset_type = asset.asset_type

    # get selected objects
    armature, meshes = bpy_util.get_selected_armature_and_meshes()

    if armature is None and ('Skelet' in asset_type or asset_type == 'AnimSequence'):
        raise RuntimeError('Select an armature.')
    if meshes == [] and 'Mesh' in asset_type:
        raise RuntimeError('Select meshes.')
    if 'Mesh' not in asset_type and asset_type not in ['Skeleton', 'AnimSequence']:
        raise RuntimeError(f'Unsupported asset. ({asset_type})')

    if asset_type in ['Skeleton', 'AnimSequence']:
        meshes = []
    if asset_type == 'AnimSequence':
        inject_animation(asset, armature, ue_version, rescale=rescale)
    else:
        # check uv count
        uv_counts = [len(mesh.data.uv_layers) for mesh in meshes]
        if len(list(set(uv_counts))) > 1:
            raise RuntimeError('All meshes should have the same number of uv maps')

        primitives = get_primitives(asset, armature, meshes,
                                    rescale=rescale,
                                    only_mesh=only_mesh)
        print('Editing asset data...')
        asset.uexp.import_from_blender(primitives, only_mesh=only_mesh)

        bpy_util.deselect_all()
        bpy_util.select_objects([armature] + meshes)

    actual_name = os.path.basename(asset.actual_path)

    if duplicate_folder_structure:
        dirs = asset.asset_path.split('/')
        if dirs[0] == '':
            dirs = dirs[2:]
        else:
            dirs = dirs[1:]
        dirs = dirs[:-1]
        dirs = '\\'.join(dirs)
        asset_path = os.path.join(directory, mod_name,
                                  content_folder, dirs, actual_name)
    else:
        asset_path = os.path.join(directory, actual_name)

    asset.save(asset_path)
    return asset_type


class InjectOptions(PropertyGroup):
    """Properties for inject options."""
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
        default=True,
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

    rescale: FloatProperty(
        name='Rescale',
        description='Rescale mesh and skeleton',
        default=1, min=0.01, max=100, step=0.01, precision=2,
    )


class InjectToUasset(Operator):
    """Operator to inject objects to .uasset files."""
    bl_idname = 'inject.uasset'
    bl_label = 'Export .uasset here'
    bl_description = 'Inject a selected asset to .uasset file'
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name="target_dir",
        default=''
    )

    def draw(self, context):
        """Draw options for file picker."""
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
        """Invoke."""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        """Inject selected objects into a selected file."""
        start_time = time.time()
        general_options = context.scene.general_options
        if bpy_util.os_is_windows():
            bpy.ops.wm.console_toggle()
            bpy.ops.wm.console_toggle()
        try:
            general_options = context.scene.general_options
            inject_options = context.scene.inject_options
            asset_type = inject_uasset(general_options.source_file,
                                       self.directory,
                                       ue_version=general_options.ue_version,
                                       rescale=inject_options.rescale,
                                       only_mesh=inject_options.only_mesh,
                                       duplicate_folder_structure=inject_options.duplicate_folder_structure,
                                       mod_name=inject_options.mod_name,
                                       content_folder=inject_options.content_folder)
            elapsed_s = f'{(time.time() - start_time):.2f}s'
            msg = f'Success! Injected {asset_type} in {elapsed_s}'
            print(msg)
            self.report({'INFO'}, msg)
            ret = {'FINISHED'}

        except ImportError as exc:
            self.report({'ERROR'}, exc.args[0])
            ret = {'CANCELLED'}
        return ret


class SelectUasset(Operator):
    """File picker for source file."""
    bl_idname = 'select.uasset'
    bl_label = 'Select Uasset'
    bl_description = 'Select .uasset file you want to mod'

    filter_glob: StringProperty(default='*.uasset', options={'HIDDEN'})

    filepath: StringProperty(
        name='File Path'
    )

    def invoke(self, context, event):
        """Invoke."""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        """Update file path."""
        context.scene.general_options.source_file = self.filepath
        return {'FINISHED'}


class UASSET_PT_inject_panel(bpy.types.Panel):
    """UI panel for inject function."""
    bl_label = "Inject to Uasset"
    bl_idname = 'VIEW3D_PT_inject_uasset'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uasset"

    def draw(self, context):
        """Draw UI panel."""
        layout = self.layout

        # import_uasset.py->GeneralOptions
        general_options = context.scene.general_options

        layout.operator(InjectToUasset.bl_idname, text='Inject to Uasset (Experimantal)',
                        icon='MESH_DATA')
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(general_options, 'ue_version')
        col.prop(general_options, 'source_file')
        layout.operator(SelectUasset.bl_idname, text='Select Source File', icon='FILE')


classes = (
    InjectOptions,
    InjectToUasset,
    SelectUasset,
    UASSET_PT_inject_panel,
)


def register():
    """Regist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.inject_options = PointerProperty(type=InjectOptions)


def unregister():
    """Unregist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.inject_options
