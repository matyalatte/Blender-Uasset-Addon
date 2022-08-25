"""UI panel and operator to import .uasset files."""

import os
import time

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Operator, PropertyGroup
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector, Quaternion, Matrix
import numpy as np

from . import bpy_util, unreal, util
from .texconv.texconv import Texconv

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
    return 0.01 * rescale / bpy.context.scene.unit_settings.scale_length


def generate_armature(name, bones, normalize_bones=True, rotate_bones=False,
                      minimal_bone_length=0.025, rescale=1.0):
    """Add a skeleton to scene.

    Args:
        name (string): armature name
        bones (list[unreal.skeleton.Bone]): bone data
        normalize_bones (bool): Force all bones to have the same length
        rotate_bones (bool): Rotate all bones by 90 degrees
        minimal_bone_length (float): Force all bones to be longer than this value
        rescale (float): rescale factor for bone positions

    Returns:
        amt (bpy.types.Armature): Added armature
    """
    print('Generating an armature...')

    amt = bpy_util.add_armature(name=name)
    rescale_factor = get_rescale_factor(rescale)

    def cal_trs(bone):
        trans = Vector((bone.trans[0], -bone.trans[1], bone.trans[2])) * rescale_factor
        rot = Quaternion((-bone.rot[3], bone.rot[0], -bone.rot[1], bone.rot[2]))
        scale = Vector((bone.scale[0], bone.scale[1], bone.scale[2]))
        bone.trs = bpy_util.make_trs(trans, rot, scale)
        bone.trans = trans
    list(map(cal_trs, bones))

    def cal_length(bone, bones):
        if len(bone.children) == 0:
            bone.length = rescale_factor
            return
        length = 0
        for child_id in bone.children:
            child = bones[child_id]
            length += child.trans.length
        length /= len(bone.children)
        bone.length = length
    list(map(lambda b: cal_length(b, bones), bones))

    if rotate_bones:  # looks fine in blender, but bad in UE4
        # Todo: still looks bad for some assets
        local_bone_vec = Vector((1, 0, 0))
        z_axis = Vector((0, 1, 0))
    else:  # looks fine in UE4, but bad in blender
        local_bone_vec = Vector((0, 1, 0))
        z_axis = Vector((0, 0, 1))

    def mult_vec(vec1, vec2):
        return Vector((x1 * x2 for x1, x2 in zip(vec1, vec2)))

    minimal_bone_length *= rescale / bpy.context.scene.unit_settings.scale_length
    minimal_bone_length *= (1 + normalize_bones)

    def cal_global_matrix(root, global_matrix, bones):
        root.global_matrix = global_matrix @ root.trs
        root.head = global_matrix @ root.trans
        root.tail = root.global_matrix @ (local_bone_vec * root.length)
        root.z_axis_tail = root.global_matrix @ (z_axis * root.length)

        if normalize_bones or (root.tail - root.head).length < minimal_bone_length:
            trans, rot, scale = root.global_matrix.decompose()
            trans = mult_vec(trans, scale)
            trs = bpy_util.make_trs(trans, rot, Vector((1, 1, 1)))
            root.tail = trs @ (local_bone_vec * minimal_bone_length)
            root.z_axis_tail = trs @ (z_axis * minimal_bone_length)

        for child_id in root.children:
            child = bones[child_id]
            cal_global_matrix(child, root.global_matrix, bones)

    cal_global_matrix(bones[0], Matrix.Identity(4), bones)

    def generate_bones(amt, root, bones, parent=None):
        new_b = bpy_util.add_bone(amt, root.name, root.head, root.tail, root.z_axis_tail, parent=parent)
        for child_id in root.children:
            child = bones[child_id]
            generate_bones(amt, child, bones, parent=new_b)
    generate_bones(amt, bones[0], bones)
    return amt


def load_utexture(file, name, version, asset=None, invert_normals=False, no_err=True, texconv=None):
    """Import a texture form .uasset file.

    Args:
        file (string): file path to .uasset file
        name (string): texture name
        version (string): UE version
        asset (unreal.uasset.Uasset): loaded asset data
        invert_normals (bool): Flip y axis if the texture is normal map.
        texconv (Texconv): Texture converter for dds.

    Returns:
        tex (bpy.types.Image): loaded texture
        tex_type (string): texture type

    Notes:
        if asset is None, it will load .uasset file
        if it's not None, it will get texture data from asset
    """
    temp = util.io_util.make_temp_file(suffix='.dds')
    if texconv is None:
        texconv = Texconv()
    if asset is not None:
        name = asset.name
        file = name
    try:
        if asset is None:
            asset = unreal.uasset.Uasset(file, version=version, asset_type='Texture')
        utex = asset.uexp.texture
        utex.remove_mipmaps()
        if 'BC5' in utex.type:
            tex_type = 'NORMAL'
        elif 'BC4' in utex.type:
            tex_type = 'GRAY'
        else:
            tex_type = 'COLOR'
        dds = unreal.dds.DDS.asset_to_DDS(asset)
        dds.save(temp)
        tga_file = texconv.convert_to_tga(temp, utex.format_name, utex.uasset.asset_type,
                                          out=os.path.dirname(temp), invert_normals=invert_normals)
        if tga_file is None:  # if texconv doesn't exist
            tex = bpy_util.load_dds(tga_file, name=name, tex_type=tex_type, invert_normals=invert_normals)
        else:
            tex = bpy_util.load_tga(tga_file, name=name)
    except Exception as e:
        if not no_err:
            raise e
        print(f'Failed to load {file}')
        tex = None
        tex_type = None

    if os.path.exists(temp):
        os.remove(temp)
    if os.path.exists(tga_file):
        os.remove(tga_file)
    return tex, tex_type


def generate_materials(asset, version, load_textures=False,
                       invert_normal_maps=False, suffix_list=(['_C', '_D'], ['_N'], ['_A'])):
    """Add materials and textures, and make shader nodes.

    args:
        asset (unreal.uasset.Uasset): mesh asset
        version (string): UE version
        load_textures (bool): if import texture files or not
        invert_normal_maps (bool): if flip y axis for normal maps or not
        suffix_list (list[list[string]]): suffix list for color map, normal maps, and alpha textures

    Returns:
        materials (list[bpy.types.Material]): Added materials
        material_names (list[string]): material names
    """
    if load_textures:
        print('Loading textures...')
        texconv = Texconv()
    # add materials to mesh
    material_names = [m.import_name for m in asset.uexp.mesh.materials]
    color_gen = bpy_util.ColorGenerator()
    materials = [bpy_util.add_material(name, color_gen) for name in material_names]
    texture_num = sum(len(m.texture_asset_paths) for m in asset.uexp.mesh.materials)
    progress = 1
    texs = {}

    def contain_suffix(base_name, names, suffix_list):
        for suf in suffix_list:
            if base_name + suf in names:
                return names.index(base_name + suf)
        return -1

    def has_suffix(name, suffix_list):
        for suf in suffix_list:
            if name[-len(suf):] == suf:
                return True
        return False

    for m, ue_m in zip(materials, asset.uexp.mesh.materials):
        m['class'] = ue_m.class_name
        m['asset_path'] = ue_m.asset_path
        m['slot_name'] = ue_m.slot_name
        for i, p in zip(range(len(ue_m.texture_asset_paths)), ue_m.texture_asset_paths):
            m['texture_path_' + str(i)] = p
        if load_textures:
            names = []
            material_name = os.path.basename(ue_m.asset_path)
            for tex_path, asset_path in zip(ue_m.texture_actual_paths, ue_m.texture_asset_paths):
                print(f'[{progress}/{texture_num}]', end='')
                progress += 1
                name = os.path.basename(asset_path)
                if name in texs:
                    print(f'Texture is already loaded ({tex_path})')
                    names.append(name)
                    continue
                if not os.path.exists(tex_path):
                    print(f'Texture not found ({tex_path})')
                    continue
                tex, tex_type = load_utexture(tex_path, os.path.basename(asset_path),
                                              version, invert_normals=invert_normal_maps, texconv=texconv)
                if tex is not None:
                    texs[name] = (tex, tex_type)
                    names.append(name)

            types = [texs[n][1] for n in names]

            # Todo: refine codes
            def search_suffix(suffix, tex_type, new_type_suffix, types, names, material_name, need_suffix=False):
                """Search main textures that shuold be connected to shaders."""
                if tex_type not in types:
                    return types
                index = None
                type_names = [n for n, t in zip(names, types) if t == tex_type]
                new_id = contain_suffix(material_name, type_names, suffix)
                if new_id != -1:
                    # exist "material_name + suffix" in texture names.
                    index = names.index(type_names[new_id])
                if index is None:
                    names_has_suf = [n for n in type_names if has_suffix(n, suffix)]
                    if len(names_has_suf) > 0:
                        # exist textures has the suffix.
                        index = names.index(names_has_suf[0])
                    elif need_suffix:
                        # not found suffix and no need main textures.
                        return types
                if index is None:
                    # not found suffix but need a main texture.
                    index = names.index(type_names[0])
                types[index] += new_type_suffix
                print(f'{types[index]}: {names[index]}')
                return types

            types = search_suffix(suffix_list[0], 'COLOR', '_MAIN', types, names, material_name)
            types = search_suffix(suffix_list[1], 'NORMAL', '_MAIN', types, names, material_name)
            types = search_suffix(suffix_list[2], 'GRAY', '_ALPHA', types, names, material_name, need_suffix=True)

            height = 300
            for name, tex_type in zip(names, types):
                tex, _ = texs[name]
                # no need to invert normals if it is already inverted.
                bpy_util.assign_texture(tex, m, tex_type=tex_type, location=[-800, height],
                                        invert_normals=not invert_normal_maps)
                height -= 300
    return materials, material_names


def generate_mesh(amt, asset, materials, material_names, rescale=1.0,
                  keep_sections=False, smoothing=True):
    """Add meshes to scene.

    Args:
        amt (bpy.types.Armature): target armature
        asset (unreal.uasset.Uasset): source asset
        materials (list[bpy.types.Material]): material objects
        material_names (list[string]): material names
        rescale (float): rescale factor for vertex positions
        keep_sections (bool): split mesh by materials or not
        smoothing (bool): apply smooth shading or not

    Returns:
        mesh (bpy.types.Mesh): A mesh object
    """
    print('Generating meshes...')
    # get mesh data from asset
    material_ids, _ = asset.uexp.mesh.LODs[0].get_meta_for_blender()
    normals, positions, texcoords, vertex_groups, joints, weights, indices = \
        asset.uexp.mesh.LODs[0].parse_buffers_for_blender()

    rescale_factor = get_rescale_factor(rescale)

    if amt is not None:
        bone_names = [b.name for b in asset.uexp.mesh.skeleton.bones]

    sections = []
    collection = bpy.context.view_layer.active_layer_collection.collection
    for material_id, i in zip(material_ids, range(len(material_ids))):
        name = material_names[material_id]
        section = bpy_util.add_empty_mesh(amt, name, collection=collection)
        sections.append(section)
        if amt is not None:
            mod = section.modifiers.new(name='Armature', type='ARMATURE')
            mod.object = amt

        mesh_data = section.data
        mesh_data.materials.append(materials[material_id])

        pos = np.array(positions[i], dtype=np.float32) * rescale_factor
        pos = bpy_util.flip_y_for_3d_vectors(pos)
        indice = np.array(indices[i], dtype=np.uint32)
        uv_maps = np.array([uv[i] for uv in texcoords], dtype=np.float32)
        uv_maps = bpy_util.flip_uv_maps(uv_maps)
        bpy_util.construct_mesh(mesh_data, pos, indice, uv_maps)

        if amt is not None:
            # skinning
            vg_names = [bone_names[vg] for vg in vertex_groups[i]]
            joint = np.array(joints[i], dtype=np.uint32)
            weight = np.array(weights[i], dtype=np.float32) / 255  # Should we use float64 like normals?
            bpy_util.skinning(section, vg_names, joint, weight)

        # smoothing
        normal = np.array(normals[i], dtype=np.float64) / 127 - 1  # Got broken normals with float32
        normal = bpy_util.flip_y_for_3d_vectors(normal)
        bpy_util.smoothing(mesh_data, len(indice) // 3, normal, enable_smoothing=smoothing)

    if not keep_sections:
        # join meshes
        sections[0].name = asset.name
        sections[0].data.name = asset.name
        bpy_util.join_meshes(sections)

    return sections[0]


def load_acl_track(pose_bone, ue_bone, data_path, values, times, action,
                   rescale_factor=1.0, rotation_format='QUATERNION'):
    """Load acl track for an element."""
    def vec_sub(a, b):
        return [a_ - b_ for a_, b_ in zip(a, b)]

    def vec_div(a, b):
        return [a_ / b_ for a_, b_ in zip(a, b)]

    path_from_pb = pose_bone.path_from_id(data_path)
    fcurves = bpy_util.get_fcurves(action, path_from_pb, 3 + (rotation_format == 'QUATERNION'))

    for val, t in zip(values, times):
        if 'rotation' in data_path:
            val[1] = - val[1]
            norm = sum(x*x for x in val)
            if norm > 1:
                quat = [0] + val
            else:
                quat = [- np.sqrt(1 - norm)] + val
            anim_quat = Quaternion(quat)
            quat = ue_bone.rot
            default_quat = Quaternion([-quat[3], quat[0], -quat[1], quat[2]])
            quat_diff = default_quat.rotation_difference(anim_quat)

            if rotation_format == 'QUATERNION':
                new_val = quat_diff
            else:
                new_val = quat_diff.to_euler()
        elif data_path == 'location':
            trans_diff = vec_sub(val, ue_bone.trans)
            trans_diff = Vector([trans_diff[0], -trans_diff[1], trans_diff[2]])
            trans_diff *= rescale_factor
            quat = ue_bone.rot
            default_quat = Quaternion([-quat[3], quat[0], -quat[1], quat[2]])
            trans_diff = default_quat.conjugated() @ trans_diff

            new_val = trans_diff
        elif data_path == 'scale':
            scale_diff = vec_div(val, ue_bone.scale)
            new_val = scale_diff
        bpy_util.set_vector_to_fcurves(fcurves, new_val, t)


def load_acl_bone_track(pose_bone, ue_bone, track, action, start_frame=0, interval=1,
                        rescale_factor=1.0, rotation_format='QUATERNION',
                        only_first_frame=False):
    """Load acl track for a bone."""
    data_paths = ['rotation_quaternion', 'location', 'scale']
    if rotation_format != 'QUATERNION':
        data_paths[0] = 'rotation_euler'
    constant_id = 0
    track_data_id = 0
    for use_default, use_constant, data_path in zip(track.use_default, track.use_constant, data_paths):
        if use_default:
            continue
        if use_constant:
            frames = [track.constant_list[constant_id * 3: (constant_id + 1) * 3]]
            constant_id += 1
        else:
            frames = track.track_data[track_data_id]
            track_data_id += 1
        if only_first_frame:
            frames = [frames[0]]
        times = [t * interval + start_frame for t in range(len(frames))]
        load_acl_track(pose_bone, ue_bone, data_path, frames, times, action,
                       rescale_factor=rescale_factor, rotation_format=rotation_format)


def load_bone_track(pose_bone, ue_bone, track, action, start_frame=0, interval=1,
                    rescale_factor=1.0, rotation_format='QUATERNION',
                    only_first_frame=False):
    """Load acl track for a bone."""
    data_paths = ['rotation_quaternion', 'location', 'scale']
    if rotation_format != 'QUATERNION':
        data_paths[0] = 'rotation_euler'
    for keys, times, data_path in zip(track.keys, track.times, data_paths):
        if len(keys) == 0:
            continue
        if only_first_frame:
            keys = [keys[0]]
            if len(times) > 0:
                times = [times[0]]
        if len(times) == 0:
            times = [i for i in range(len(keys))]
        times = [t * interval + start_frame for t in times]
        load_acl_track(pose_bone, ue_bone, data_path, keys, times, action,
                       rescale_factor=rescale_factor, rotation_format=rotation_format)


def load_animation(anim, armature, ue_version, rescale=1.0, ignore_missing_bones=False,
                   start_frame_option='DEFAULT', rotation_format='QUATERNION',
                   ignore_root_bone=False, import_as_nla=False,
                   only_first_frame=False):
    """Import animation data."""
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

    if ue_version not in ['ff7r', 'kh3']:
        raise RuntimeError(f'Animations are unsupported for this verison. ({ue_version})')

    # Get pose bones
    bpy_util.move_to_object_mode()
    bpy_util.move_to_pose_mode(armature)
    pose_bones = armature.pose.bones
    for pb in pose_bones:
        pb.rotation_mode = rotation_format

    # Get animation data
    bone_ids = anim.bone_ids
    compressed_data = anim.compressed_data
    num_samples = anim.num_frames
    print(f'frame count: {num_samples}')

    # Check required bones
    if not ignore_missing_bones:
        for bone_id in bone_ids:
            if bone_id >= len(bones):
                raise RuntimeError(f'Bone index out of range. (anim bone id: {bone_id}, num bones: {len(bones)})')
            bone = bones[bone_id]
            if bone.name not in pose_bones:
                raise RuntimeError(f'A required bone not found in the selected armature. ({bone.name})')

    # Check fps
    scene_fps = bpy_util.get_fps()
    if anim.is_acl:
        anim_fps = compressed_data.clip_header.sample_rate
    else:
        anim_fps = 30
    interval = max(scene_fps // anim_fps, 1)
    if scene_fps % anim_fps != 0:
        new_fps = interval * anim_fps
        print(f'Changed FPS from {scene_fps} to {new_fps}.')
        bpy_util.set_fps(new_fps)

    # Set frame info
    scene = bpy.context.scene
    if start_frame_option == 'CURRENT':
        start_frame = scene.frame_current
    elif start_frame_option == 'DEFAULT':
        start_frame = scene.frame_start
    else:
        start_frame = 1

    # Get action
    anim_name = anim.get_animation_name()
    if import_as_nla:
        action = bpy.data.actions.new(name=anim_name)
        nla_track = bpy_util.add_nla_track(armature, name=anim_name)
        end_frame = max((num_samples - 1) * interval, 1)
        _ = bpy_util.add_nla_strip(nla_track, anim_name, start_frame, action, end=end_frame)
        start_frame = 0
    else:
        if armature.animation_data is None:
            armature.animation_data_create()
        if armature.animation_data.action is None:
            action = bpy.data.actions.new(name=armature.name)
            armature.animation_data.action = action
        else:
            action = armature.animation_data.action

    # Intert key frames to the action
    print('Inserting key frames...')
    rescale_factor = get_rescale_factor(rescale)
    for track, bone_id in zip(compressed_data.bone_tracks, bone_ids):
        bone = bones[bone_id]
        if bone_id == 0 and ignore_root_bone:
            print(f'Tracks for {bone.name} have been ignored.')
            continue
        if bone.name not in pose_bones:
            if ignore_missing_bones:
                print(f'Found a missing bone. Tracks for {bone.name} have been ignored.')
                continue
        pb = pose_bones[bone.name]
        if anim.is_acl:
            load_acl_bone_track(pb, bone, track, action, start_frame=start_frame, interval=interval,
                                rescale_factor=rescale_factor, rotation_format=rotation_format,
                                only_first_frame=only_first_frame)
        else:
            load_bone_track(pb, bone, track, action, start_frame=start_frame, interval=interval,
                            rescale_factor=rescale_factor, rotation_format=rotation_format,
                            only_first_frame=only_first_frame)


def load_uasset(file, rename_armature=True, keep_sections=False,
                normalize_bones=True, rotate_bones=False,
                minimal_bone_length=0.025, rescale=1.0,
                smoothing=True, only_skeleton=False,
                show_axes=False, bone_display_type='OCTAHEDRAL', show_in_front=True,
                load_textures=False, invert_normal_maps=False, ue_version='4.18',
                suffix_list=(['_C', '_D'], ['_N'], ['_A']),
                ignore_missing_bones=False, start_frame_option='DEFAULT',
                rotation_format='QUATERNION', ignore_root_bone=False,
                import_as_nla=False, only_first_frame=False,
                verbose=False):
    """Import assets form .uasset file.

    Notes:
        See property groups for the description of arguments
    """
    # load .uasset
    asset = unreal.uasset.Uasset(file, version=ue_version, verbose=verbose)
    asset_type = asset.asset_type
    print(f'Asset type: {asset_type}')

    if 'Texture' in asset_type:
        tex, _ = load_utexture('', '', ue_version, asset=asset, invert_normals=invert_normal_maps, no_err=False)
        return tex, asset_type
    if 'Material' in asset_type:
        raise RuntimeError(f'Unsupported asset. ({asset.asset_type})')
    if 'AnimSequence' in asset_type:
        anim = asset.uexp.anim
        selected = bpy.context.selected_objects
        amt_list = [obj for obj in selected if obj.type == 'ARMATURE']
        if len(amt_list) != 1:
            raise RuntimeError('Select an armature to import an animation.')
        armature = amt_list[0]
        load_animation(anim, armature, ue_version, rescale=rescale,
                       ignore_missing_bones=ignore_missing_bones, start_frame_option=start_frame_option,
                       rotation_format=rotation_format, ignore_root_bone=ignore_root_bone,
                       import_as_nla=import_as_nla, only_first_frame=only_first_frame)
        return armature, asset_type

    if asset_type not in ['SkeletalMesh', 'Skeleton', 'StaticMesh']:
        raise RuntimeError(f'Unsupported asset. ({asset.asset_type})')
    if asset.uexp.mesh is None and only_skeleton:
        raise RuntimeError('"Only Skeleton" option is checked, but the asset has no skeleton.')

    asset.uexp.load_material_asset()

    bpy_util.move_to_object_mode()

    # add a skeleton to scene
    if asset.uexp.skeleton is not None:
        bones = asset.uexp.skeleton.bones
        amt = generate_armature(asset.name, bones, normalize_bones,
                                rotate_bones, minimal_bone_length, rescale=rescale)
        amt.data.show_axes = show_axes
        amt.data.display_type = bone_display_type
        amt.show_in_front = show_in_front
        if rename_armature:
            amt.name = 'Armature'
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        amt = None

    # add a mesh to scene
    if asset.uexp.mesh is not None and not only_skeleton:
        materials, material_names = generate_materials(asset, ue_version,
                                                       load_textures=load_textures,
                                                       invert_normal_maps=invert_normal_maps,
                                                       suffix_list=suffix_list)
        mesh = generate_mesh(amt, asset, materials, material_names, rescale=rescale,
                             keep_sections=keep_sections, smoothing=smoothing)

    # return root object
    if amt is None:
        root = mesh
    else:
        root = amt
    root['class'] = asset.asset_type
    root['asset_path'] = asset.asset_path
    root['actual_path'] = asset.actual_path
    return root, asset.asset_type


class UassetImportPanelFlags(PropertyGroup):
    """Properties to manage tabs."""
    ui_general: BoolProperty(name='General', default=True)
    ui_mesh: BoolProperty(name='Mesh', default=True)
    ui_texture: BoolProperty(name='Texture', default=False)
    ui_armature: BoolProperty(name='Armature', default=False)
    ui_animation: BoolProperty(name='Animation', default=False)
    ui_scale: BoolProperty(name='Scale', default=False)


class UassetGeneralOptions(PropertyGroup):
    """Properties for general options."""
    ue_version: EnumProperty(
        name='UE version',
        items=(('ff7r', 'FF7R', ''),
               ('kh3', 'KH3', ''),
               ('4.18', '4.18 (Experimental!)', 'Not Recommended'),
               ('4.27', '4.26, 4.27 (Experimental!)', 'Not Recommended'),
               ('5.0', '5.0 (Experimental!)', 'Not Recommended')),
        description='UE version of assets',
        default='ff7r'
    )

    source_file: StringProperty(
        name='Source file',
        description=(
            'Path to .uasset file you want to mod'
        ),
        default='',
    )

    verbose: BoolProperty(
        name='Verbose',
        description=(
            "Show the parsing result in the console.\n"
            'Note that "print()" is a very slow function.'
        ),
        default=False,
    )


class UassetImportOptions(PropertyGroup):
    """Properties for import options."""
    rename_armature: BoolProperty(
        name='Rename Armature',
        description=(
            "Rename armature to 'Armature'.\n"
            "If the asset is skeleton or you check 'Keep Sections',\n"
            'this flag will be ignored'
        ),
        default=True,
    )

    smoothing: BoolProperty(
        name='Apply Smooth shading',
        description=(
            'Apply smooth shading'
        ),
        default=True,
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

    invert_normal_maps: BoolProperty(
        name='Invert Normal Maps',
        description=(
            'Flip Y axis for normal maps.\n'
            'No need shader nodes to invert G channel,\n'
            "But the textures won't work in the games"
        ),
        default=False,
    )

    suffix_for_color: StringProperty(
        name='Suffix for color map',
        description=(
            'The suffix will be used to determine which 3ch texture is the main color map'
        ),
        default='_C, _D, d00',
    )

    suffix_for_normal: StringProperty(
        name='Suffix for normal map',
        description=(
            'The suffix will be used to determine which 2ch texture is the main normal map'
        ),
        default='_N, n00',
    )

    suffix_for_alpha: StringProperty(
        name='Suffix for alpha texture',
        description=(
            'The suffix will be used to detect alpha texture'
        ),
        default='_A',
    )

    minimal_bone_length: FloatProperty(
        name='Minimal Bone Length',
        description='Force all bones to be longer than this value',
        default=0.025, min=0.01, max=1, step=0.005, precision=3,
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
            "Won't import mesh"
        ),
        default=False,
    )

    show_axes: BoolProperty(
        name='Show Bone Axes',
        description=(
            'Display bone axes'
        ),
        default=False,
    )

    show_in_front: BoolProperty(
        name='Show In Front',
        description=(
            'Display bones in front of other objects'
        ),
        default=True,
    )

    bone_display_type: EnumProperty(
        name='Bone Display Type',
        items=(('OCTAHEDRAL', 'Octahedral', ' Display bones as octahedral shape'),
               ('STICK', 'Stick', 'Display bones as simple 2D lines with dots'),
               ('BBONE', 'B-Bone', 'Display bones as boxes, showing subdivision and B-Splines'),
               ('ENVELOPE', 'Envelope',
                'Display bones as extruded spheres, showing deformation influence volume'),
               ('WIRE', 'Wire', 'Display bones as thin wires, showing subdivision and B-Splines')),
        description='Appearance of bones',
        default='STICK'
    )

    unit_scale: EnumProperty(
        name='Unit Scale',
        items=(('CENTIMETERS', 'Centimeters', 'UE standard'),
               ('METERS', 'Meters', 'Blender standard'),
               ('NONE', 'No Change', 'Use the current uint scale')),
        description='Change unit scale to',
        default='NONE'
    )

    rescale: FloatProperty(
        name='Rescale',
        description='Rescale mesh and skeleton',
        default=1, min=0.01, max=100, step=0.01, precision=2,
    )

    start_frame_option: EnumProperty(
        name='Start Frame',
        items=(('DEFAULT', 'Default', 'Use the start frame of the scene'),
               ('CURRENT', 'Current', 'Use the current frame'),
               ('FIRST', '1', 'Use 1 for the start frame')),
        description='Start frame for the animation clip',
        default='DEFAULT'
    )

    rotation_format: EnumProperty(
        name='Rotation Format',
        items=(('QUATERNION', 'Quaternion',
                'UE Standard.\nNo Gimbal Lock but Blender does NOT support slerp interpolation for key frames'),
               ('XYZ', 'Euler (XYZ)', 'Blender Standard.\nGood interpolation but prone to Gimbal Lock')),
        description='Rotation format for pose bones',
        default='QUATERNION'
    )

    ignore_missing_bones: BoolProperty(
        name='Ignore Missing Bones',
        description=(
            "When off, it will raise an error if the selected armature does NOT have all animated bones"
        ),
        default=True,
    )

    ignore_root_bone: BoolProperty(
        name='Ignore Root Bone',
        description=(
            "Ignore root bone tracks.\n"
            "It might be able to make the animation cyclic"
        ),
        default=False,
    )

    import_as_nla: BoolProperty(
        name='Import as NLA',
        description="Import the animation as an NLA track",
        default=False,
    )

    only_first_frame: BoolProperty(
        name='Only the First Frame',
        description="Import only the first frame.",
        default=False,
    )


class UASSET_OT_import_uasset(Operator, ImportHelper):
    """Operator to import .uasset files."""
    bl_idname = 'uasset.import_uasset'
    bl_label = 'Import Uasset'
    bl_description = 'Import .uasset files'
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(default='*.uasset', options={'HIDDEN'})

    files: CollectionProperty(
        name='File Path',
        type=bpy.types.OperatorFileListElement,
    )

    def draw(self, context):
        """Draw options for file picker."""
        layout = self.layout

        layout.use_property_split = False
        layout.use_property_decorate = False  # No animation.

        win_m = bpy.context.window_manager.uasset_import_panel_flags
        goption = context.scene.uasset_general_options
        ioption = context.scene.uasset_import_options
        options = [goption] + [ioption] * 5
        show_flags = [
            win_m.ui_general, win_m.ui_mesh, win_m.ui_texture,
            win_m.ui_armature, win_m.ui_animation, win_m.ui_scale
        ]
        labels = ['ui_general', 'ui_mesh', 'ui_texture', 'ui_armature', 'ui_animation', 'ui_scale']
        props = [
            ['ue_version', 'verbose'],
            ['load_textures', 'keep_sections', 'smoothing'],
            ['invert_normal_maps', 'suffix_for_color', 'suffix_for_normal', 'suffix_for_alpha'],
            ['rotate_bones', 'minimal_bone_length', 'normalize_bones',
             'rename_armature', 'only_skeleton', 'show_axes', 'bone_display_type', 'show_in_front'],
            ['start_frame_option', 'rotation_format', 'import_as_nla',
             'ignore_root_bone', 'ignore_missing_bones', 'only_first_frame'],
            ['unit_scale', 'rescale']
        ]

        for option, show_flag, label, prop_list in zip(options, show_flags, labels, props):
            box = layout.box()
            row = box.row(align=True)
            row.alignment = 'LEFT'
            row.prop(win_m, label, icon='DOWNARROW_HLT' if show_flag else 'RIGHTARROW', emboss=False)
            if show_flag:
                box.use_property_split = True
                box.use_property_decorate = False
                for prop in prop_list:
                    box.prop(option, prop)

    def invoke(self, context, event):
        """Invoke."""
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        """Run the operator."""
        if bpy_util.os_is_windows():
            bpy.ops.wm.console_toggle()
            bpy.ops.wm.console_toggle()
        return self.import_uasset(context)

    def import_uasset(self, context):
        """Import a file."""
        file = self.filepath
        try:
            start_time = time.time()
            general_options = context.scene.uasset_general_options
            import_options = context.scene.uasset_import_options

            bpy_util.set_unit_scale(import_options.unit_scale)

            def str_to_list(list_as_str):
                list_as_str = list_as_str.replace(' ', '')
                list_as_str = list_as_str.replace('　', '')
                return list_as_str.split(',')

            suffix_list = [str_to_list(import_options.suffix_for_color),
                           str_to_list(import_options.suffix_for_normal),
                           str_to_list(import_options.suffix_for_alpha)]
            _, asset_type = load_uasset(
                file,
                rename_armature=import_options.rename_armature,
                keep_sections=import_options.keep_sections,
                normalize_bones=import_options.normalize_bones,
                rotate_bones=import_options.rotate_bones,
                minimal_bone_length=import_options.minimal_bone_length,
                rescale=import_options.rescale,
                smoothing=import_options.smoothing,
                only_skeleton=import_options.only_skeleton,
                show_axes=import_options.show_axes,
                show_in_front=import_options.show_in_front,
                bone_display_type=import_options.bone_display_type,
                load_textures=import_options.load_textures,
                invert_normal_maps=import_options.invert_normal_maps,
                ue_version=general_options.ue_version,
                suffix_list=suffix_list,
                ignore_missing_bones=import_options.ignore_missing_bones,
                ignore_root_bone=import_options.ignore_root_bone,
                start_frame_option=import_options.start_frame_option,
                rotation_format=import_options.rotation_format,
                import_as_nla=import_options.import_as_nla,
                only_first_frame=import_options.only_first_frame,
                verbose=general_options.verbose
            )

            context.scene.uasset_general_options.source_file = file

            elapsed_s = f'{(time.time() - start_time):.2f}s'
            m = f'Success! Imported {asset_type} in {elapsed_s}'
            print(m)
            self.report({'INFO'}, m)
            ret = {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret


class UASSET_OT_toggle_console(Operator):
    """Operator to toggle the system console."""
    bl_idname = 'uasset.toggle_console'
    bl_label = 'Toggle Console'
    bl_description = ('Toggle the system console.\n'
                      'I recommend enabling the system console to see the progress')

    def execute(self, context):
        """Toggle console."""
        if bpy_util.os_is_windows():
            bpy.ops.wm.console_toggle()
        return {'FINISHED'}


class UASSET_PT_import_panel(bpy.types.Panel):
    """UI panel for improt function."""
    bl_label = "Import Uasset"
    bl_idname = 'UASSET_PT_import_panel'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uasset"

    def draw(self, context):
        """Draw UI panel."""
        layout = self.layout
        layout.operator(UASSET_OT_import_uasset.bl_idname, icon='MESH_DATA')
        general_options = context.scene.uasset_general_options
        import_options = context.scene.uasset_import_options
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(general_options, 'ue_version')
        col.prop(import_options, 'load_textures')
        col.prop(import_options, 'keep_sections')

        layout.separator()
        if bpy_util.os_is_windows():
            layout.operator(UASSET_OT_toggle_console.bl_idname, icon='CONSOLE')


def menu_func_import(self, context):
    """Add import operator to File->Import."""
    self.layout.operator(UASSET_OT_import_uasset.bl_idname, text='Uasset (.uasset)')


classes = (
    UassetImportPanelFlags,
    UassetGeneralOptions,
    UassetImportOptions,
    UASSET_OT_import_uasset,
    UASSET_OT_toggle_console,
    UASSET_PT_import_panel,
)


def register():
    """Regist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.WindowManager.uasset_import_panel_flags = PointerProperty(type=UassetImportPanelFlags)
    bpy.types.Scene.uasset_general_options = PointerProperty(type=UassetGeneralOptions)
    bpy.types.Scene.uasset_import_options = PointerProperty(type=UassetImportOptions)


def unregister():
    """Unregist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.unregister_class(c)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    del bpy.types.WindowManager.uasset_import_panel_flags
    del bpy.types.Scene.uasset_general_options
    del bpy.types.Scene.uasset_import_options
