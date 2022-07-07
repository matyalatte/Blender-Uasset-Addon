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


def load_utexture(file, name, version, asset=None, invert_normals=False):
    """Import a texture form .uasset file.

    Args:
        file (string): file path to .uasset file
        name (string): texture name
        version (string): UE version
        asset (unreal.uasset.Uasset): loaded asset data
        invert_normals (bool): Flip y axis if the texture is normal map.

    Returns:
        tex (bpy.types.Image): loaded texture
        tex_type (string): texture type

    Notes:
        if asset is None, it will load .uasset file
        if it's not None, it will get texture data from asset
    """
    temp = util.io_util.make_temp_file(suffix='.dds')
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
        dds = unreal.dds.DDS.asset_to_DDS(utex)
        dds.save(temp)
        tex = bpy_util.load_dds(temp, name=name, tex_type=tex_type, invert_normals=invert_normals)
    except Exception:
        print(f'Failed to load {file}')
        tex = None
        tex_type = None

    if os.path.exists(temp):
        os.remove(temp)
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
    # add materials to mesh
    material_names = [m.import_name for m in asset.uexp.mesh.materials]
    color_gen = bpy_util.ColorGenerator()
    materials = [bpy_util.add_material(name, color_gen) for name in material_names]
    texture_num = sum([len(m.texture_asset_paths) for m in asset.uexp.mesh.materials])
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
                                              version, invert_normals=invert_normal_maps)
                if tex is not None:
                    texs[name] = (tex, tex_type)
                    names.append(name)

            types = [texs[n][1] for n in names]

            def search_suffix(suffix, tex_type, new_type_suffix, types, names, material_name, need_suffix=False):
                if tex_type not in types:
                    return
                index = None
                type_names = [n for n, t in zip(names, types) if t == tex_type]
                new_id = contain_suffix(material_name, type_names, suffix)
                if new_id != -1:
                    index = new_id
                if index is None:
                    names_has_suf = [n for n in type_names if has_suffix(n, suffix)]
                    if len(names_has_suf) > 0:
                        index = names.index(names_has_suf[0])
                    elif need_suffix:
                        return
                if index is None:
                    index = names.index(type_names[0])
                if index is not None:
                    types[index] += new_type_suffix
                    print(f'{types[index]}: {names[index]}')
            search_suffix(suffix_list[0], 'COLOR', '_MAIN', types, names, material_name)
            search_suffix(suffix_list[1], 'NORMAL', '_MAIN', types, names, material_name)
            search_suffix(suffix_list[2], 'GRAY', '_ALPHA', types, names, material_name, need_suffix=True)

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
        bpy_util.smoothing(mesh_data, len(indice) // 3, normal, enable_smoothing=smoothing)

    if not keep_sections:
        # join meshes
        sections[0].name = asset.name
        sections[0].data.name = asset.name
        bpy_util.join_meshes(sections)

    return sections[0]


def load_uasset(file, rename_armature=True, keep_sections=False,
                normalize_bones=True, rotate_bones=False,
                minimal_bone_length=0.025, rescale=1.0,
                smoothing=True, only_skeleton=False,
                show_axes=False, bone_display_type='OCTAHEDRAL', show_in_front=True,
                load_textures=False, invert_normal_maps=False, ue_version='4.18',
                suffix_list=(['_C', '_D'], ['_N'], ['_A'])):
    """Import assets form .uasset file.

    Notes:
        See property groups for the description of arguments
    """
    # load .uasset
    asset = unreal.uasset.Uasset(file, version=ue_version)
    asset_type = asset.asset_type
    print(f'Asset type: {asset_type}')

    if 'Texture' in asset_type:
        tex, _ = load_utexture('', '', ue_version, asset=asset, invert_normals=invert_normal_maps)
        return tex, asset_type
    if 'Material' in asset_type:
        raise RuntimeError(f'Unsupported asset. ({asset.asset_type})')

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
    return root, asset.asset_type


class TABFLAGS_WindowManager(PropertyGroup):
    """Properties to manage tabs."""
    ui_general: BoolProperty(name='General', default=True)
    ui_mesh: BoolProperty(name='Mesh', default=True)
    ui_texture: BoolProperty(name='Texture', default=False)
    ui_armature: BoolProperty(name='Armature', default=False)
    ui_scale: BoolProperty(name='Scale', default=False)


class GeneralOptions(PropertyGroup):
    """Properties for general options."""
    ue_version: EnumProperty(
        name='UE version',
        items=(('ff7r', 'FF7R', ''),
               ('4.18', '4.18 (Experimental!)', 'Not Recommended'),
               ('4.27', '4.27 (Experimental!)', 'Not Recommended'),
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


class ImportOptions(PropertyGroup):
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
        default='_C, _D',
    )

    suffix_for_normal: StringProperty(
        name='Suffix for normal map',
        description=(
            'The suffix will be used to determine which 2ch texture is the main normal map'
        ),
        default='_N',
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


class ImportUasset(Operator, ImportHelper):
    """Operator to import .uasset files."""
    bl_idname = 'import.uasset'
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

        win_m = bpy.context.window_manager.tabflags
        goption = context.scene.general_options
        ioption = context.scene.import_options
        options = [goption] + [ioption] * 4
        show_flags = [win_m.ui_general, win_m.ui_mesh, win_m.ui_texture, win_m.ui_armature, win_m.ui_scale]
        labels = ['ui_general', 'ui_mesh', 'ui_texture', 'ui_armature', 'ui_scale']
        props = [
            ['ue_version'],
            ['load_textures', 'keep_sections', 'smoothing'],
            ['invert_normal_maps', 'suffix_for_color', 'suffix_for_normal', 'suffix_for_alpha'],
            ['rotate_bones', 'minimal_bone_length', 'normalize_bones',
             'rename_armature', 'only_skeleton', 'show_axes', 'bone_display_type', 'show_in_front'],
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
        """Import files."""
        if self.files:
            # Multiple file import
            ret = {'CANCELLED'}
            dirname = os.path.dirname(self.filepath)
            for file in self.files:
                path = os.path.join(dirname, file.name)
                if self.unit_import(path, context) == {'FINISHED'}:
                    ret = {'FINISHED'}
            return ret

        # Single file import
        return self.unit_import(self.filepath, context)

    def unit_import(self, file, context):
        """Import a file."""
        try:
            start_time = time.time()
            general_options = context.scene.general_options
            import_options = context.scene.import_options

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
                suffix_list=suffix_list
            )

            context.scene.general_options.source_file = file

            elapsed_s = f'{(time.time() - start_time):.2f}s'
            m = f'Success! Imported {asset_type} in {elapsed_s}'
            print(m)
            self.report({'INFO'}, m)
            ret = {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret


class ToggleConsole(Operator):
    """Operator to toggle the system console."""
    bl_idname = 'import.toggle_console'
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
    bl_idname = 'VIEW3D_PT_import_uasset'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uasset"

    def draw(self, context):
        """Draw UI panel."""
        layout = self.layout
        layout.operator(ImportUasset.bl_idname, icon='MESH_DATA')
        general_options = context.scene.general_options
        import_options = context.scene.import_options
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(general_options, 'ue_version')
        col.prop(import_options, 'load_textures')
        col.prop(import_options, 'keep_sections')

        layout.separator()
        if bpy_util.os_is_windows():
            layout.operator(ToggleConsole.bl_idname, icon='CONSOLE')


def menu_func_import(self, context):
    """Add import operator to File->Import."""
    self.layout.operator(ImportUasset.bl_idname, text='Uasset (.uasset)')


classes = (
    TABFLAGS_WindowManager,
    GeneralOptions,
    ImportOptions,
    ImportUasset,
    ToggleConsole,
    UASSET_PT_import_panel,
)


def register():
    """Regist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.WindowManager.tabflags = PointerProperty(type=TABFLAGS_WindowManager)
    bpy.types.Scene.general_options = PointerProperty(type=GeneralOptions)
    bpy.types.Scene.import_options = PointerProperty(type=ImportOptions)


def unregister():
    """Unregist UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.unregister_class(c)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    del bpy.types.WindowManager.tabflags
    del bpy.types.Scene.general_options
    del bpy.types.Scene.import_options
