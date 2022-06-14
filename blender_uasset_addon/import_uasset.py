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
from bpy_extras.io_utils import ImportHelper
import os

from . import bpy_util, uasset, texture, util
if "bpy" in locals():
    import importlib
    if "bpy_util" in locals():
        importlib.reload(bpy_util)
    if "uasset" in locals():
        importlib.reload(uasset)
    if "texture" in locals():
        importlib.reload(texture)
    if "util" in locals():
        importlib.reload(util)

def get_rescale_factor(rescale):
    return 0.01 * rescale / bpy.context.scene.unit_settings.scale_length

#add a skeleton to scene
def generate_armature(name, bones, normalize_bones=True, rotate_bones=False, minimal_bone_length=0.025, rescale=1.0):
    print('Generating an armature...')

    amt = bpy_util.add_armature(name = name)
    rescale_factor = get_rescale_factor(rescale)
    
    def cal_trs(bone):
        trans = Vector((bone.trans[0], -bone.trans[1], bone.trans[2])) * rescale_factor
        rot = Quaternion((bone.rot[3], -bone.rot[0], bone.rot[1], -bone.rot[2]))
        scale = Vector((bone.scale[0], bone.scale[1], bone.scale[2]))
        bone.trs = Matrix.LocRotScale(trans, rot, scale)
        bone.trans = trans
    list(map(lambda b: cal_trs(b), bones))
            
    def cal_length(bone, bones):
        if len(bone.children)==0:
            bone.length = rescale_factor
            return
        length = 0
        for c in bone.children:
            child = bones[c]
            length += child.trans.length
        length /= len(bone.children)
        bone.length = length
    list(map(lambda b: cal_length(b, bones), bones))

    if rotate_bones: #looks fine in blender, but bad in UE4
        local_bone_vec = Vector((1, 0, 0))
        z_axis = Vector((0, 1, 0))
    else: #looks fine in UE4, but bad in blender
        local_bone_vec = Vector((0, 1, 0))
        z_axis = Vector((0, 0, 1))

    def mult_vec(vec1, vec2):
        return Vector((x1*x2 for x1, x2 in zip(vec1, vec2)))   

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
            trs = Matrix.LocRotScale(trans, rot, Vector((1,1,1)))
            root.tail = trs @ (local_bone_vec * minimal_bone_length)
            root.z_axis_tail = trs @ (z_axis * minimal_bone_length)

        for c in root.children:
            child = bones[c]
            cal_global_matrix(child, root.global_matrix, bones)

    cal_global_matrix(bones[0], Matrix.Identity(4), bones)

    def generate_bones(amt, root, bones, parent = None):
        b = bpy_util.add_bone(amt, root.name, root.head, root.tail, root.z_axis_tail, parent = parent)
        for c in root.children:
            child = bones[c]
            generate_bones(amt, child, bones, parent = b)
    generate_bones(amt, bones[0], bones)
    return amt

def load_utexture(file, name):
    temp = util.io_util.make_temp_file(suffix='.dds')
    try:
        utex = texture.utexture.Utexture(file, version='ff7r')
        utex.remove_mipmaps()
        if 'BC5' in utex.type:
            type='NORMAL'
        elif 'BC4' in utex.type:
            type='GRAY'
        else:
            type='COLOR'
        dds = texture.dds.DDS.asset_to_DDS(utex)
        dds.save(temp)
        tex = bpy_util.load_dds(temp, name=name, type=type)
    except:
        print('Failed to load {}'.format(file))
        tex = None
        type = None
    
    if os.path.exists(temp):
        os.remove(temp)
    return tex, type

def setup_materials(asset, load_textures=False):
    print('Loading textures...')
    #add materials to mesh
    material_names = [m.import_name for m in asset.mesh.materials]
    color_gen = bpy_util.ColorGenerator()
    materials = [bpy_util.add_material(name, color_gen) for name in material_names]
    texture_num = sum([len(m.texture_asset_paths) for m in asset.mesh.materials])
    progress = 1
    texs = {}
    for m, ue_m in zip(materials, asset.mesh.materials):
        m['class'] = ue_m.class_name
        m['asset_path'] = ue_m.asset_path
        m['slot_name'] = ue_m.slot_name
        for i, p in zip(range(len(ue_m.texture_asset_paths)), ue_m.texture_asset_paths):
            m['texture_path_'+str(i)]=p
        if load_textures:
            names = []
            material_name = os.path.basename(ue_m.asset_path)
            for tex_path, asset_path in zip(ue_m.texture_actual_paths, ue_m.texture_asset_paths):
                print('[{}/{}]'.format(progress, texture_num), end='')
                progress+=1
                name = os.path.basename(asset_path)
                if name in texs:
                    print('Texture is already loaded ({})'.format(asset_path))
                    names.append(name)
                    continue
                if not os.path.exists(tex_path):
                    print('Texture not found ({})'.format(asset_path))
                    continue
                tex, type = load_utexture(tex_path, os.path.basename(asset_path))
                if tex is not None:
                    texs[name]=(tex, type)
                    names.append(name)

            types = [texs[n][1] for n in names]
            print(types)

            def search_suffix(suffix, type, new_suf, need_suffix=False):
                if type not in types:
                    return
                id = None
                if material_name+suffix in names:
                    id = names.index(material_name+suffix)
                    if types[id]!=type:
                        id = None
                if id is None:
                    ns = [n for n in names if suffix in n]
                    if len(ns)>0:
                        id = names.index(ns[0])
                        if types[id]!=type:
                            id = None
                    elif need_suffix:
                        return
                if id is None:
                    ns = [n for n,t in zip(names, types) if t==type]
                    id = names.index(ns[0])
                if id is not None:
                    types[id]+='_' + new_suf
                    print('{}: {}'.format(types[id], names[id]))
            search_suffix('_C', 'COLOR', 'MAIN')
            search_suffix('_N', 'NORMAL', 'MAIN')
            search_suffix('_A', 'GRAY', 'ALPHA', need_suffix=True)
        
            y=300
            for name, type in zip(names, types):
                tex, _ = texs[name]
                bpy_util.assign_texture(tex, m, type=type, location=[-700, y])
                y -= 300

    return materials, material_names

#add meshes to scene
def generate_mesh(amt, asset, materials, material_names, rescale=1.0, keep_sections=False, shading='SMOOTH'):

    print('Generating meshes...')
    #get mesh data from asset
    material_ids, _ = asset.mesh.LODs[0].get_meta_for_blender()
    normals, positions, texcoords, vertex_groups, joints, weights, indices = asset.mesh.LODs[0].parse_buffers_for_blender()

    rescale_factor = get_rescale_factor(rescale)
    y_invert = np.array((1, -1, 1))

    if amt is not None:
        bone_names = [b.name for b in asset.mesh.skeleton.bones]

    sections = []
    collection = bpy.context.view_layer.active_layer_collection.collection

    for i in range(len(material_ids)):
        material_id = material_ids[i]
        name = material_names[material_id]
        section = bpy_util.add_empty_mesh(amt, name, collection=collection)
        sections.append(section)
        if amt is not None:
            mod = section.modifiers.new(name='Armature', type='ARMATURE')
            mod.object = amt

        mesh_data = section.data
        mesh_data.materials.append(materials[material_id])

        pos = np.array(positions[i], dtype=np.float32) * y_invert * rescale_factor
        indice = np.array(indices[i], dtype=np.uint32)
        uv_maps = [uv[i] for uv in texcoords]
        uv_maps = np.array((0, 1)) + np.array(uv_maps, dtype=np.float32) * np.array((1, -1))
        bpy_util.construct_mesh(mesh_data, pos, indice, uv_maps)

        if amt is not None:
            #skinning
            vg_names = [bone_names[vg] for vg in vertex_groups[i]]
            joint = np.array(joints[i], dtype=np.uint32)
            weight = np.array(weights[i], dtype=np.uint32) / 255
            bpy_util.skinning(section, vg_names, joint, weight)
        
        #smoothing
        norm = np.array(normals[i], dtype=np.float32) / 127 - 1
        norm *= y_invert
        bpy_util.smoothing(mesh_data, len(indice)//3, norm, shading=shading=='SMOOTH')
        

    if not keep_sections:
        #join meshes
        sections[0].name=asset.name
        sections[0].data.name=asset.name
        bpy_util.join_meshes(sections)

    return sections[0]
        
#add mesh asset to scene
def load_uasset(file, rename_armature=True, keep_sections=False, \
    normalize_bones=True, rotate_bones=False, \
    minimal_bone_length=0.025, rescale=1.0, \
    shading='SMOOTH', only_skeleton=False, \
    show_axes=False, bone_display_type='OCTAHEDRAL', \
    load_textures=False):
    
    #load .uasset
    asset=uasset.uexp.MeshUexp(file)
    asset_type = asset.asset_type
    print('Asset type: {}'.format(asset_type))
    if asset_type not in ['SkeletalMesh', 'Skeleton', 'StaticMesh']:
        raise RuntimeError('Unsupported asset. ({})'.format(asset.asset_type))
    if asset.mesh is None and only_skeleton:
        raise RuntimeError('"Only Skeleton" option is checked, but the asset has no skeleton.')

    bpy.context.view_layer.objects.active = bpy.context.view_layer.objects[0]
    bpy.ops.object.mode_set(mode='OBJECT')

    #add a skeleton to scene
    if keep_sections or (not rename_armature) or asset_type=='Skeleton':
        name = asset.name
    else:
        name = 'Armature'

    if asset.skeleton is not None:
        bones = asset.skeleton.bones
        amt = generate_armature(name, bones, normalize_bones, rotate_bones, minimal_bone_length, rescale=rescale)
        amt.data.show_axes = show_axes
        amt.data.display_type = bone_display_type
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        amt = None

    #add a mesh to scene
    if asset.mesh is not None and not only_skeleton:
        materials, material_names = setup_materials(asset, load_textures=load_textures)
        mesh = generate_mesh(amt, asset, materials, material_names, rescale=rescale, keep_sections=keep_sections, shading=shading)
    
    #return root object
    if amt is None:
        root = mesh
    else:
        root = amt
    root['class'] = asset.asset_type
    root['asset_path'] = asset.asset_path
    return root

class TABFLAGS_WindowManager(PropertyGroup):
    ui_mesh : BoolProperty(name='Mesh', default=True)
    ui_armature : BoolProperty(name='Armature', default=False)
    ui_scale : BoolProperty(name='Scale', default=False)

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
        try:
            start_time = time.time()
            bpy_util.set_unit_scale(import_settings['unit_scale'])

            amt = load_uasset(file, \
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
            m = 'uasset import finished in ' + elapsed_s
            self.report({'INFO'}, m)
            ret = {'FINISHED'}

        except ImportError as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret

class UASSET_PT_import_panel(bpy.types.Panel):
    bl_label = "Import Uasset"
    bl_idname = 'VIEW3D_PT_import_uasset'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uasset"
    
    def draw(self, context):
        layout = self.layout
        layout.operator(ImportUasset.bl_idname, icon = 'MESH_DATA')

def menu_func_import(self, context):
    self.layout.operator(ImportUasset.bl_idname, text='Uasset (.uasset)')

classes = (
    TABFLAGS_WindowManager,
    ImportUasset,
    UASSET_PT_import_panel,
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