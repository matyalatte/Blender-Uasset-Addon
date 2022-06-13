import bpy
import numpy as np
import os, math
from mathutils import Vector, Quaternion, Matrix

from . import uasset
from . import texture
if 'bpy' in locals():
    import importlib
    importlib.reload(uasset)
    importlib.reload(texture)

UNIT = {
    'METERS': 1,
    'CENTIMETERS': 0.01
}

def set_unit_scale(unit_scale):
    if type(unit_scale)==type(''):
        if unit_scale not in UNIT:
            raise RuntimeError('Unsupported unit. ({})'.format(unit_scale))
        unit_scale = UNIT[unit_scale]
    bpy.context.scene.unit_settings.scale_length=unit_scale

def add_armature(name='Armature', location = (0,0,0)):
    bpy.ops.object.armature_add(
        enter_editmode=True,
        location=location
    )
    amt = bpy.context.object
    amt.rotation_mode = 'QUATERNION'
    amt.name = name
    amt_data = amt.data
    amt_data.name = name
    amt_data.display_type = 'STICK'
    return amt

def add_bone(amt, name, head, tail, z_axis_tail, parent = None):
    b = amt.data.edit_bones.new(name)
    b.use_deform = True
    b.head = head
    b.tail = tail
    
    z_axis = z_axis_tail - head
    b.align_roll(z_axis)
    if parent is not None:
        b.parent = parent
    return b

def get_rescale_factor(rescale):
    return 0.01 * rescale / bpy.context.scene.unit_settings.scale_length

#add a skeleton to scene
def generate_armature(name, bones, normalize_bones=True, rotate_bones=False, minimal_bone_length=0.025, rescale=1.0):
    print('Generating an armature...')

    amt = add_armature(name = name)
    amt.data.edit_bones.remove(amt.data.edit_bones[0])
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
        b = add_bone(amt, root.name, root.head, root.tail, root.z_axis_tail, parent = parent)
        for c in root.children:
            child = bones[c]
            generate_bones(amt, child, bones, parent = b)
    generate_bones(amt, bones[0], bones)
    return amt

def add_empty_mesh(amt, name, collection=None):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.rotation_mode = 'QUATERNION'
    obj.show_name = True
    if collection is None:
        collection = bpy.context.scene.collection
    collection.objects.link(obj)
    if amt is not None:
        obj.parent = amt
    m = obj.matrix_world.copy()
    obj.matrix_local @= m
    return obj

#color generator
#https://martin.ankerl.com/2009/12/09/how-to-create-random-colors-programmatically/
class ColorGenerator:
    def __init__(self):
        self.h=0

    def hsv_to_rgb(h, s, v):
        h_i = int(h*6)
        f = h*6 - h_i
        p = v * (1 - s)
        q = v * (1 - f*s)
        t = v * (1 - (1 - f) * s)
        if h_i==0:
            r, g, b = v, t, p
        elif h_i==1:
            r, g, b = q, v, p
        elif h_i==2:
            r, g, b = p, v, t
        elif h_i==3:
            r, g, b = p, q, v
        elif h_i==4:
            r, g, b = t, p, v
        elif h_i==5:
            r, g, b = v, p, q
        return [r, g, b]

    golden_ratio_conjugate = 0.618033988749895
    def gen_new_color(self):
        self.h += ColorGenerator.golden_ratio_conjugate
        self.h %= 1
        r,g,b = ColorGenerator.hsv_to_rgb(self.h, 0.5, 0.95)
        return (r, g, b, 1)

def add_material(name, color_gen):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = color_gen.gen_new_color()
    nodes = m.node_tree.nodes
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Specular'].default_value =0.0
    m.use_backface_culling = True
    m.blend_method='HASHED'
    m.shadow_method='HASHED'
    return m

def load_dds(file, name, type='COLOR'):
    tex = bpy.data.images.load(file)
    tex.file_format = 'BMP'
    tex.name = name
    
    if type=='NORMAL':
        #reconstruct z (x*x+y*y+z*z=1)
        pix = np.array(tex.pixels, dtype=np.float32)
        pix = pix.reshape((-1, 4))
        xy = pix[:,[0,1]] * 2 - 1 #(0,1)->(-1,1)
        squared = np.square(xy)
        z = 1 - squared[:,0] - squared[:,1]
        pix[:,2] = (np.sqrt(np.clip(z, 0, None))+ 1) * 0.5 #(-1,1)->(0,1)
        pix = pix.flatten()
        tex.pixels = np.clip(pix, None, 1)

    elif type=='GRAY':
        #copy r to g and b
        pix = np.array(tex.pixels)
        pix = pix.reshape((-1, 4))
        pix[:, [1, 2]]=pix[:, [0, 0]]
        pix = pix.flatten()
        tex.pixels = pix

    tex.pack()
    tex.filepath=''
    tex.filepath_raw=''
    return tex

#add shader node for texture to material
def assign_texture(tex, mat, type='COLOR', location=[-800, 300]):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get('Principled BSDF')
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = tex
    tex_node.location = location

    if type=='COLOR_MAIN':
        links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])
    if 'NORMAL' in type:    
        curve_node = nodes.new('ShaderNodeRGBCurve')
        curve_node.location = [location[0] + 300, location[1]]
        curve_node.mapping.curves[1].points[0].location=(0,1)
        curve_node.mapping.curves[1].points[1].location=(1,0)
        curve_node.mapping.update()
        normal_node = nodes.new('ShaderNodeNormalMap')
        normal_node.location = [location[0] + 600, location[1]]
        links.new(curve_node.inputs['Color'], tex_node.outputs['Color'])
        links.new(normal_node.inputs['Color'], curve_node.outputs['Color'])
        if 'MAIN' in type:
            links.new(bsdf.inputs['Normal'], normal_node.outputs['Normal'])
    if 'ALPHA' in type:
        links.new(bsdf.inputs['Alpha'], tex_node.outputs['Color'])

def load_utexture(file, name):
    temp = os.path.join(os.path.dirname(file), '__temp__.dds')
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
        tex = load_dds(temp, name=name, type=type)
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
    color_gen = ColorGenerator()
    materials = [add_material(name, color_gen) for name in material_names]
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
                assign_texture(tex, m, type=type, location=[-700, y])
                y -= 300

    return materials, material_names

#add meshes to scene
def generate_mesh(amt, asset, materials, material_names, rescale=1.0, keep_sections=False, shading='SMOOTH'):

    print('Generating meshes...')
    #get mesh data from asset
    material_ids, uv_num = asset.mesh.LODs[0].get_meta_for_blender()
    normals, positions, texcoords, vertex_groups, joints, weights, indices = asset.mesh.LODs[0].parse_buffers_for_blender()

    rescale_factor = get_rescale_factor(rescale)
    y_invert = np.array((1, -1, 1))

    def flatten(ary):
        return ary.reshape(ary.size)

    if amt is not None:
        def assign_vg(vertex_id, vertex_groups, j, w):
            if w>0:
                vertex_groups[j].add([vertex_id], w, 'REPLACE')
        bones = asset.mesh.skeleton.bones

    sections = []
    section_data_list = []
    collection = bpy.context.view_layer.active_layer_collection.collection
    for i in range(len(material_ids)):
        name = material_names[material_ids[i]]
        section = add_empty_mesh(amt, name, collection=collection)
        sections.append(section)
        if amt is not None:
            mod = section.modifiers.new(name='Armature', type='ARMATURE')
            mod.object = amt

        data = section.data
        section_data_list.append(data)
        data.materials.append(materials[material_ids[i]])
        indice = indices[i]

        pos = np.array(positions[i], dtype=np.float32) * y_invert * rescale_factor
        norm = np.array(normals[i], dtype=np.float32) / 127 - 1
        norm *= y_invert
        indice = np.array(indice, dtype=np.uint32)
        texcoord = [uv[i] for uv in texcoords]
        uvs = np.array((0, 1)) + np.array(texcoord, dtype=np.float32) * np.array((1, -1))

        face_num = len(indice)//3

        #add mesh data
        data.vertices.add(len(pos))
        data.vertices.foreach_set('co', flatten(pos))

        data.loops.add(len(indice))
        data.loops.foreach_set('vertex_index', indice)

        data.polygons.add(face_num)
        loop_starts = np.arange(0, 3 * face_num, step=3)
        loop_totals = np.full(face_num, 3)
        data.polygons.foreach_set('loop_start', loop_starts)
        data.polygons.foreach_set('loop_total', loop_totals)

        #add uv maps
        for j in range(uv_num):
            name = 'UVMap{}'.format(j)
            layer = data.uv_layers.new(name=name)
            uv = uvs[j][indice]
            layer.data.foreach_set('uv', flatten(uv))
        
        #add vertex groups
        if amt is not None:
            vertex_group = vertex_groups[i]
            for vg in vertex_group:
                section.vertex_groups.new(name=bones[vg].name)
            vgs = list(section.vertex_groups)

            #skinning
            joint = np.array(joints[i], dtype=np.uint32)
            weight = np.array(weights[i], dtype=np.uint32) / 255
            for vi, js, ws in zip(range(len(joint)), joint, weight):
                list(map(lambda j,w: assign_vg(vi, vgs, j, w), js, ws))
        
        #smoothing
        smooth = np.empty(face_num, dtype=np.bool)
        smooth.fill(shading=='SMOOTH')

        data.polygons.foreach_set('use_smooth', smooth)

        data.validate()
        data.update()

        data.create_normals_split()
        data.normals_split_custom_set_from_vertices(norm)

        data.use_auto_smooth = shading=='SMOOTH'

    if not keep_sections:
        #join meshes
        sections[0].name=asset.name
        sections[0].data.name=asset.name
        ctx = bpy.context.copy()
        ctx['active_object'] = sections[0]
        ctx['selected_editable_objects'] = sections
        bpy.ops.object.join(ctx)

        #remove unnecessary mesh data
        bpy.ops.object.select_all(action='DESELECT')
        for s in section_data_list[1:]:
            bpy.data.meshes.remove(s)

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
        amt.data.name = asset.name
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

