import bpy
from mathutils import Vector, Quaternion, Matrix
import numpy as np

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

def os_is_windows():
    import sys
    return sys.platform in ['win32', 'cygwin', 'msys']

def update_window():
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

def move_to_object_mode():
    if bpy.context.mode=='OBJECT':
        return
    objs = [obj for obj in bpy.context.view_layer.objects if obj.visible_get()]
    if len(objs)>0:
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode='OBJECT')

def deselect_all():
    bpy.ops.object.select_all(action='DESELECT')

def select_objects(objs):
    for obj in objs:
        if obj is None:
            continue
        obj.select_set(True)
    return

def get_meshes(armature):
    if armature is None:
        return []
    if armature.type!='ARMATURE':
        raise RuntimeError('Not an armature.')
    meshes=[child for child in armature.children if child.type=='MESH']
    return meshes

def get_armature(mesh):
    parent = mesh.parent
    if parent is not None and parent.type!='ARMATURE':
        raise RuntimeError('Not an armature.')
    return parent

#select an armature -> return the armature and its meshes
#select meshes -> return their armature and the selected meshes
#select an armature and meshes -> return themselves
def get_selected_armature_and_meshes():
    selected = bpy.context.selected_objects
    amt_list = [obj for obj in selected if obj.type=='ARMATURE']
    meshes = [obj for obj in selected if obj.type=='MESH']
    if len(amt_list)>1:
        raise RuntimeError('Multiple armatures are selected.')
    parents = [get_armature(mesh) for mesh in meshes]
    parents = list(set(parents))
    if len(parents)>1:
        raise RuntimeError('All selected meshes should have the same armature.')

    if len(amt_list)==0:
        if len(parents)==0:
            armature = None
        else:
            armature = parents[0]
    else:
        armature = amt_list[0]
    if len(meshes)==0:
        meshes = get_meshes(armature)
    return armature, meshes

def split_mesh_by_materials(mesh):
    if len(mesh.data.materials)==0:
        raise RuntimeError('Mesh have no materials.')
    if len(mesh.data.materials)==1:
        return [mesh]
    move_to_object_mode()
    deselect_all()
    mesh.select_set(True)
    bpy.ops.mesh.separate(type='MATERIAL')
    return bpy.context.selected_objects

#vectors: 2d numpy array (-1, 3 or 4)
def flip_y_for_3d_vectors(vectors):
    vectors[:,1]*=-1
    return vectors

#uv_maps: 3d numpy array (uv_count, vertex_count, 2)
def flip_uv_maps(uv_maps):
    uv_maps[:, :, 1] *= -1
    uv_maps[:, :, 1] += 1
    return uv_maps

def get_uv_maps(mesh_data):
    layers = mesh_data.uv_layers
    uv_count = len(layers)
    uvs = np.empty((uv_count, len(mesh_data.loops) * 2), dtype=np.float32)
    for layer, uv in zip(layers, uvs):
        layer.data.foreach_get('uv', uv)
    uvs = uvs.reshape(uv_count, len(mesh_data.loops), 2)
    return uvs

def get_positions(mesh_data, rescale=1.0):
    vertex_count = len(mesh_data.vertices)
    positions = np.empty(vertex_count * 3, dtype=np.float32)
    mesh_data.vertices.foreach_get('co', positions)
    positions = positions.reshape(vertex_count, 3) * rescale
    return positions

def get_normals(mesh_data):
    #need to calculate tangents and normals
    
    vertex_count = len(mesh_data.loops)

    normals = np.empty(vertex_count * 3, dtype=np.float32)
    mesh_data.loops.foreach_get('normal', normals)
    normals = normals.reshape(vertex_count, 3)

    tangents = np.empty(vertex_count * 3, dtype=np.float32)
    mesh_data.loops.foreach_get('tangent', tangents)
    tangents = tangents.reshape(vertex_count, 3)

    signs = np.empty(vertex_count, dtype=np.float32)
    mesh_data.loops.foreach_get('bitangent_sign', signs)
    signs = signs.reshape((vertex_count, 1))

    return normals, tangents, signs

def get_triangle_indices(mesh_data):
    indices = np.empty(len(mesh_data.loops), dtype=np.uint32)
    mesh_data.loops.foreach_get('vertex_index', indices)
    return indices

def get_vertex_weight(vertex, vg_id_to_bone_id):
    joint = []
    weight = []
    if not vertex.groups:
        return [[], []]

    def get_vg_info(group_element):
        w = group_element.weight
        j = vg_id_to_bone_id[group_element.group]
        if j==-1 or weight==0:
            return
        joint.append(j)
        weight.append(w)

    list(map(lambda x: get_vg_info(x), vertex.groups))
    return [joint, weight]

#todo: too slow (it will take 75% of runtime)
def get_weights(mesh, bone_names):
    mesh_data = mesh.data
    mesh_vgs = mesh.vertex_groups
    def f(n, list):
        if n in list:
            return list.index(n)
        else:
            return -1
    vg_id_to_bone_id = [f(vg.name, bone_names) for vg in mesh_vgs]

    influences = [get_vertex_weight(v, vg_id_to_bone_id) for v in mesh_data.vertices]
    joints = [i[0] for i in influences]
    weights = [i[1] for i in influences]
    vertex_groups = list(set(sum(joints,[])))
    joints = [[vertex_groups.index(j) for j in joint] for joint in joints]
    max_influence_count = max([len(j) for j in joints])
    return vertex_groups, joints, weights, max_influence_count

def add_armature(name='Armature', location = (0,0,0)):
    bpy.ops.object.armature_add(
        enter_editmode=True,
        location=location
    )
    amt = bpy.context.object
    amt.rotation_mode = 'QUATERNION'
    amt.name = name
    amt.data.name = name
    amt.data.edit_bones.remove(amt.data.edit_bones[0])
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

#assign mesh data to an empty mesh
#  mesh_data: (bpy.types.Mesh).data
#  positions: 2d numpy array for vertex positions (vertex_count, 3)
#  indices: 1d numpy array for triangle indices (face_count*3)
#  uv_maps: 3d numpy array for uv maps (uv_count, vertex_count, 2)
def construct_mesh(mesh_data, positions, indices, uv_maps):
    face_num = len(indices)//3

    mesh_data.vertices.add(len(positions))
    mesh_data.vertices.foreach_set('co', positions.flatten())

    mesh_data.loops.add(len(indices))
    mesh_data.loops.foreach_set('vertex_index', indices)

    mesh_data.polygons.add(face_num)
    loop_starts = np.arange(0, 3 * face_num, step=3)
    loop_totals = np.full(face_num, 3)
    mesh_data.polygons.foreach_set('loop_start', loop_starts)
    mesh_data.polygons.foreach_set('loop_total', loop_totals)

    for j in range(len(uv_maps)):
        name = 'UVMap{}'.format(j)
        layer = mesh_data.uv_layers.new(name=name)
        uv = uv_maps[j][indices]
        layer.data.foreach_set('uv', uv.flatten())
    return mesh_data

def assign_vg(vertex_id, vertex_groups, j, w):
    if w>0:
        vertex_groups[j].add([vertex_id], w, 'REPLACE')

#mesh: bpy.types.Mesh
#vg_names: string array of vertex groups
#joints: 2d numpy array of vertex group ids (vertex_count, max_influence_count)
#weights: 2d numpy array of weights (vertex_count, max_influence_count)
def skinning(mesh, vg_names, joints, weights):
    list(map(lambda name:mesh.vertex_groups.new(name=name), vg_names))
    vgs = list(mesh.vertex_groups)
    for vi, js, ws in zip(range(len(joints)), joints, weights):
        list(map(lambda j,w: assign_vg(vi, vgs, j, w), js, ws))

#meshes: an array of bpy.types.Mesh
def join_meshes(meshes):
    if len(meshes)==0:
        return None
    if len(meshes)==1:
        return meshes[0]
    mesh_data_list = [mesh.data for mesh in meshes]
    ctx = bpy.context.copy()
    ctx['active_object'] = meshes[0]
    ctx['selected_editable_objects'] = meshes
    bpy.ops.object.join(ctx)

    #remove unnecessary mesh data
    deselect_all()
    for s in mesh_data_list[1:]:
        bpy.data.meshes.remove(s)
    return meshes[0]

#mesh_data: (bpy.types.Mesh).data
#normals: 2d numpy array of normals (vertex_count, 3)
def smoothing(mesh_data, face_count, normals, smoothing=True):
    smooth = np.empty(face_count, dtype=np.bool)
    smooth.fill(smoothing)
    mesh_data.polygons.foreach_set('use_smooth', smooth)
    mesh_data.validate()
    mesh_data.update()
    mesh_data.create_normals_split()
    mesh_data.normals_split_custom_set_from_vertices(normals)
    mesh_data.use_auto_smooth = smoothing

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

def add_material(name, color_gen=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    if color_gen is not None:
        m.diffuse_color = color_gen.gen_new_color()
    nodes = m.node_tree.nodes
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Specular'].default_value =0.0
    m.use_backface_culling = True
    return m

def enable_alpha_for_material(material):
    material.blend_method='HASHED'
    material.shadow_method='HASHED'

#types
#COLOR: Color map
#NORMAL: Normal map
#GRAY: Gray scale
def load_dds(file, name, type='COLOR', color_space='Non-Color', invert_normals=False):
    tex = bpy.data.images.load(file)
    tex.pack()
    tex.colorspace_settings.name=color_space
    tex.filepath=''
    tex.filepath_raw=''

    tex.name = name
    
    if type=='NORMAL':
        #reconstruct z (x*x+y*y+z*z=1)
        print('Reconstructing normal map...')
        pix = np.array(tex.pixels, dtype=np.float32)
        pix = pix.reshape((-1, 4))
        xy = pix[:,[0,1]] * 2 - 1 #(0~1)->(-1~1)
        squared = np.square(xy)
        z = np.sqrt(np.clip(1 - squared[:,0] - squared[:,1], 0, None))
        pix[:,2] = (z + 1) * 0.5 #(-1~1)->(0~1)
        if invert_normals:
            pix[:,1]=1-pix[:,1]
        pix = pix.flatten()
        tex.pixels = pix

    elif type=='GRAY':
        print('Reconstructing gray scale map...')
        #copy r to g and b
        pix = np.array(tex.pixels)
        pix = pix.reshape((-1, 4))
        pix[:, [1, 2]]=pix[:, [0, 0]]
        pix = pix.flatten()
        tex.pixels = pix
    return tex

#types
#COLOR: Color map
#COLOR_MAIN: Main color map
#NORMAL: Normal map
#NORMAL_MAIN: Main normal map
#ALPHA: Alpha texture
def assign_texture(texture, material, type='COLOR', location=[-800, 300], invert_normals=True):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    bsdf_node = nodes.get('Principled BSDF')
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = texture
    tex_node.location = location

    if type=='COLOR_MAIN':
        links.new(bsdf_node.inputs['Base Color'], tex_node.outputs['Color'])
        tex_node.image.colorspace_settings.name='sRGB'
    if 'NORMAL' in type:
        normal_node = nodes.new('ShaderNodeNormalMap')
        if invert_normals:
            curve_node = nodes.new('ShaderNodeRGBCurve')
            curve_node.location = [location[0] + 300, location[1]]
            curve_node.mapping.curves[1].points[0].location=(0,1)
            curve_node.mapping.curves[1].points[1].location=(1,0)
            curve_node.mapping.update()
            normal_node.location = [location[0] + 600, location[1]]
            links.new(curve_node.inputs['Color'], tex_node.outputs['Color'])
            links.new(normal_node.inputs['Color'], curve_node.outputs['Color'])
        else:
            normal_node.location = [location[0] + 450, location[1]]
            links.new(normal_node.inputs['Color'], tex_node.outputs['Color'])
        if 'MAIN' in type:
            links.new(bsdf_node.inputs['Normal'], normal_node.outputs['Normal'])
    if 'ALPHA' in type:
        links.new(bsdf_node.inputs['Alpha'], tex_node.outputs['Color'])
        enable_alpha_for_material(material)

from mathutils import Matrix
# Same as Matrix.LocRotScale. but 2.8x doesn't support it.
def make_trs(trans, rot, scale):
    mat_trans = Matrix.Translation(trans)
    mat_rot = rot.to_matrix().to_4x4()
    mat_sca = Matrix.Diagonal(scale).to_4x4()
    return mat_trans @ mat_rot @ mat_sca