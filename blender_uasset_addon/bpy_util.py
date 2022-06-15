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
    mesh_data_list = [mesh.data for mesh in meshes]
    ctx = bpy.context.copy()
    ctx['active_object'] = meshes[0]
    ctx['selected_editable_objects'] = meshes
    bpy.ops.object.join(ctx)

    #remove unnecessary mesh data
    bpy.ops.object.select_all(action='DESELECT')
    for s in mesh_data_list[1:]:
        bpy.data.meshes.remove(s)

#mesh_data: (bpy.types.Mesh).data
#normals: 2d numpy array of normals (vertex_count, 3)
def smoothing(mesh_data, face_count, normals, shading=True):
    smooth = np.empty(face_count, dtype=np.bool)
    smooth.fill(shading)
    mesh_data.polygons.foreach_set('use_smooth', smooth)
    mesh_data.validate()
    mesh_data.update()
    mesh_data.create_normals_split()
    mesh_data.normals_split_custom_set_from_vertices(normals)
    mesh_data.use_auto_smooth = shading

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
    m.blend_method='HASHED'
    m.shadow_method='HASHED'
    return m

#types
#COLOR: Color map
#NORMAL: Normal map
#GRAY: Gray scale
def load_dds(file, name, type='COLOR', invert_normals=False):
    tex = bpy.data.images.load(file)
    tex.pack()    
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
        tex.pixels = np.clip(pix, 0, 1)

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

    if type!='COLOR_MAIN':
        tex_node.image.colorspace_settings.name='Non-Color'
