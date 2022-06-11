import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

from . import uasset
if "bpy" in locals():
    import importlib
    importlib.reload(uasset)

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
    amt.data.name = name
    return amt

def add_bone(amt, name, head, tail, roll, parent = None):
    b = amt.data.edit_bones.new(name)
    b.use_deform = True
    b.head = head
    b.tail = tail
    b.roll=roll
    if parent is not None:
        b.parent = parent
    return b

def add_empty_mesh(amt, name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.rotation_mode = 'QUATERNION'
    obj.show_name = True
    bpy.context.scene.collection.objects.link(obj)
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
    m.use_backface_culling = True
    return m

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
        bone.roll = rot.angle
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
    else: #looks fine in UE4, but bad in blender
        local_bone_vec = Vector((0, 1, 0))

    def mult_vec(vec1, vec2):
        return Vector((x1*x2 for x1, x2 in zip(vec1, vec2)))   

    minimal_bone_length *= rescale / bpy.context.scene.unit_settings.scale_length
    minimal_bone_length *= (1 + normalize_bones)
    def cal_global_matrix(root, global_matrix, bones):
        root.global_matrix = global_matrix @ root.trs
        root.head = global_matrix @ root.trans
        root.tail = root.global_matrix @ (local_bone_vec * root.length)

        if normalize_bones or (root.tail - root.head).length < minimal_bone_length:
            trans, rot, scale = root.global_matrix.decompose()
            trans = mult_vec(trans, scale)
            trs = Matrix.LocRotScale(trans, rot, Vector((1,1,1)))
            root.tail = trs @ (local_bone_vec * minimal_bone_length)

        for c in root.children:
            child = bones[c]
            cal_global_matrix(child, root.global_matrix, bones)

    cal_global_matrix(bones[0], Matrix.Identity(4), bones)

    def generate_bones(amt, root, bones, parent = None):
        b = add_bone(amt, root.name, root.head, root.tail, root.roll, parent = parent)
        for c in root.children:
            child = bones[c]
            generate_bones(amt, child, bones, parent = b)
    generate_bones(amt, bones[0], bones)
    return amt

#add meshes to scene
def generate_mesh(amt, asset, rescale=1.0, keep_sections=False, shading='SMOOTH'):
    print('Generating meshes...')

    #add materials to mesh
    material_names = [m.import_name for m in asset.mesh.materials]
    color_gen = ColorGenerator()
    materials = [add_material(name, color_gen) for name in material_names]
    for m, ue_m in zip(materials, asset.mesh.materials):
        m['path'] = ue_m.file_path
        m['slot_name'] = ue_m.slot_name

    #get mesh data from asset
    material_ids, uv_num = asset.mesh.LODs[0].get_meta_for_blender()
    normals, positions, texcoords, vertex_groups, joints, weights, indices = asset.mesh.LODs[0].parse_buffers_for_blender()

    rescale_factor = get_rescale_factor(rescale)
    y_invert = np.array((1, -1, 1))

    def flatten(ary):
        return ary.reshape(ary.size)

    def assign_vg(vertex_id, vertex_groups, j, w):
        if w>0:
            vertex_groups[j].add([vertex_id], w, 'REPLACE')
    if amt is not None:
        bones = asset.mesh.skeleton.bones
    sections = []
    section_data_list = []

    for i in range(len(material_ids)):
        name = material_names[material_ids[i]]
        section = add_empty_mesh(amt, name)
        sections.append(section)
        if amt is not None:
            mod = section.modifiers.new(name="Armature", type="ARMATURE")
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

        data.polygons.foreach_set("use_smooth", smooth)

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
        
#add mesh asset to scene
def load_uasset(file, rename_armature=True, keep_sections=False, normalize_bones=True, rotate_bones=False, minimal_bone_length=0.025, rescale=1.0, shading='SMOOTH'):
    
    #load .uasset
    asset=uasset.uexp.MeshUexp(file)
    asset_type = asset.asset_type
    if asset_type not in ['SkeletalMesh', 'Skeleton', 'StaticMesh']:
        raise RuntimeError('Unsupported asset. ({})'.format(asset.asset_type))

    bpy.context.view_layer.objects.active = bpy.context.view_layer.objects[0]
    bpy.ops.object.mode_set(mode='OBJECT')

    #add a skeleton to scene
    if keep_sections or rename_armature or asset_type=='Skeleton':
        name = asset.name
    else:
        name = 'Armature'

    if asset.skeleton is not None:
        bones = asset.skeleton.bones
        amt = generate_armature(name, bones, normalize_bones, rotate_bones, minimal_bone_length, rescale=rescale)
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        amt = None

    #add a mesh to scene
    if asset.mesh is not None:
        generate_mesh(amt, asset, rescale=rescale, keep_sections=keep_sections, shading=shading)
    return amt    