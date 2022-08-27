"""Utilities for Blener API."""
import sys

import bpy
from mathutils import Matrix
import numpy as np


def translate(text):
    """Translate texts."""
    return bpy.app.translations.pgettext(text, msgctxt="*")


UNIT = {
    'METERS': 1,
    'CENTIMETERS': 0.01
}


def set_unit_scale(unit_scale):
    """Change unit scale to unit_scale."""
    if isinstance(unit_scale, str):
        if unit_scale == 'NONE':
            return
        if unit_scale not in UNIT:
            raise RuntimeError(f'Unsupported unit. ({unit_scale})')
        unit_scale = UNIT[unit_scale]
    bpy.context.scene.unit_settings.scale_length = unit_scale


def os_is_windows():
    """Check if the OS is Windows."""
    return sys.platform in ['win32', 'cygwin', 'msys']


def update_window():
    """Update view port while running a process."""
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def get_fps():
    """Get fps for animations."""
    render = bpy.context.scene.render
    return render.fps / render.fps_base


def set_fps(fps):
    """Set fps for animations."""
    render = bpy.context.scene.render
    render.fps_base = max(int(render.fps_base), 1)
    render.fps = int(fps * render.fps_base)


def add_nla_track(amt, name='NLA_track'):
    """Add an NLA track to an armature."""
    if not amt.animation_data:
        amt.animation_data_create()
    nla_tracks = amt.animation_data.nla_tracks
    new_track = nla_tracks.new()
    new_track.name = name
    nla_tracks.active = new_track
    return new_track


def add_nla_strip(nla_track, name, start, action, end=None):
    """Add an NLA strip to an NLA track."""
    strip = nla_track.strips.new(name, start, action)
    if end is not None:
        strip.action_frame_end = end
    return strip


def get_fcurves(action, data_path, num_indices):
    """Add fcurves to an action."""
    def get_fc(action, data_path, index):
        curve = action.fcurves.find(data_path, index=index)
        if curve is None:
            curve = action.fcurves.new(data_path, index=index)
        return curve
    fcurves = [get_fc(action, data_path, index=i) for i in range(num_indices)]
    return fcurves


def set_vector_to_fcurves(fcurves, vec, frame):
    """Set a vector to fcurves."""
    for fc, x in zip(fcurves, vec):
        fc.keyframe_points.insert(frame, x)


def move_to_object_mode():
    """Activate a object and move to the object mode."""
    if bpy.context.mode == 'OBJECT':
        return
    objs = [obj for obj in bpy.context.view_layer.objects if obj.visible_get()]
    if len(objs) > 0:
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.mode_set(mode='OBJECT')


def move_to_pose_mode(armature):
    """Activate an armature and move to the pose mode."""
    deselect_all()
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')


def deselect_all():
    """Deselect all objects."""
    bpy.ops.object.select_all(action='DESELECT')


def get_selected_objects():
    """Get selected objects."""
    return [ob for ob in bpy.context.scene.objects if ob.select_get()]


def select_objects(objs):
    """Select objects."""
    for obj in objs:
        if obj is None:
            continue
        obj.select_set(True)


def get_meshes(armature):
    """Get child meshes from an armature."""
    if armature is None:
        return []
    if armature.type != 'ARMATURE':
        raise RuntimeError('Not an armature.')
    meshes = [child for child in armature.children if child.type == 'MESH']
    return meshes


def get_armature(mesh):
    """Get a parent armanture from a mesh."""
    parent = mesh.parent
    if parent is not None and parent.type != 'ARMATURE':
        raise RuntimeError('Not an armature.')
    return parent


def get_selected_armature_and_meshes():
    """Get selected armature and meshes.

    Returens:
        armature (bpy.types.Armature): selected armature
        meshes (list[bpy.types.Mesh]): selected meshes

    Notes:
        It will also get parent armature and child meshes.
        e.g.
        select an armature -> return the selected armature and its meshes
        select meshes -> return their armature and the selected meshes
        select an armature and meshes -> return themselves
    """
    selected = bpy.context.selected_objects
    amt_list = [obj for obj in selected if obj.type == 'ARMATURE']
    meshes = [obj for obj in selected if obj.type == 'MESH']
    if len(amt_list) > 1:
        raise RuntimeError('Multiple armatures are selected.')
    parents = [get_armature(mesh) for mesh in meshes]
    parents = list(set(parents))
    if len(parents) > 1:
        msg = 'All selected meshes should have the same armature.'
        raise RuntimeError(msg)

    if len(amt_list) == 0:
        if len(parents) == 0:
            armature = None
        else:
            armature = parents[0]
    else:
        armature = amt_list[0]
    if len(meshes) == 0:
        meshes = get_meshes(armature)
    return armature, meshes


def split_mesh_by_materials(mesh):
    """Split mesh if it has multiple materials.

    Args:
        mesh (bpy.types.Mesh): A mesh object

    Returns:
        meshes (list[bpy.types.Mesh]): Splitted mesh objects
    """
    if len(mesh.data.materials) == 0:
        raise RuntimeError('Mesh have no materials.')
    if len(mesh.data.materials) == 1:
        return [mesh]
    move_to_object_mode()
    deselect_all()
    mesh.select_set(True)
    bpy.ops.mesh.separate(type='MATERIAL')
    return bpy.context.selected_objects


def flip_y_for_3d_vectors(vectors):
    """Flip y axis for UE vectors.

    Args:
        vectors (numpy.ndarray): 2d numpy array (-1, 3 or 4)
    """
    vectors[:, 1] *= -1
    return vectors


def flip_uv_maps(uv_maps):
    """Flip y axis for UE uv maps.

    Args:
        uv_maps (numpy.ndarray): 3d numpy array (uv_count, vertex_count, 2)
    """
    uv_maps[:, :, 1] *= -1
    uv_maps[:, :, 1] += 1
    return uv_maps


def get_uv_maps(mesh_data):
    """Get uv maps form a mesh.

    Args:
        mesh_data ((bpy.types.Mesh).data): A mesh object

    Returens:
        uv_maps (numpy.ndarray): 3d numpy array (uv_count, vertex_count, 2)
    """
    layers = mesh_data.uv_layers
    uv_count = len(layers)
    uv_maps = np.empty((uv_count, len(mesh_data.loops) * 2), dtype=np.float32)
    for layer, uv_ in zip(layers, uv_maps):
        layer.data.foreach_get('uv', uv_)
    uv_maps = uv_maps.reshape((uv_count, len(mesh_data.loops), 2))
    return uv_maps


def get_positions(mesh_data, rescale=1.0):
    """Get vertex positions from a mesh.

    Args:
        mesh_data ((bpy.types.Mesh).data): A mesh object
        rescale (float): rescale factor for positions

    Returens:
        positions (numpy.ndarray): 2d numpy array (vertex_count, 3)
    """
    vertex_count = len(mesh_data.vertices)
    positions = np.empty(vertex_count * 3, dtype=np.float32)
    mesh_data.vertices.foreach_get('co', positions)
    positions = positions.reshape(vertex_count, 3) * rescale
    return positions


def get_normals(mesh_data):
    """Get vertex normals from a mesh.

    Args:
        mesh_data ((bpy.types.Mesh).data): A mesh object

    Returens:
        normals (numpy.ndarray): 2d numpy array (vertex_count, 3)
        tangents (numpy.ndarray): 2d numpy array (vertex_count, 3)
        signs (numpy.ndarray): 2d numpy array for bitangent sign (vertex_count, 1)

    Notes:
        Need to calculate tangents and normals first
    """
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
    """Get face indices from a mesh.

    Args:
        mesh_data ((bpy.types.Mesh).data): A mesh object

    Returens:
        indices (numpy.ndarray): 1d numpy array (face_count*3)

    Notes:
        Maybe the mesh should be triangulated.
    """
    indices = np.empty(len(mesh_data.loops), dtype=np.uint32)
    mesh_data.loops.foreach_get('vertex_index', indices)
    return indices


def get_vertex_weight(vertex, vg_id_to_bone_id):
    """Get skinning data form a vertex.

    Args:
        vertex (bpy.types.MeshVertex): A vertex
        vg_id_to_bone_id (list[int]): map for vertex group ids to bone ids

    Returens:
        joints (list[int]): bone ids
        weights (list[float]): bone weights
    """
    joints = []
    weights = []
    if not vertex.groups:
        return [[], []]

    def get_vg_info(group_element):
        weight = group_element.weight
        joint = vg_id_to_bone_id[group_element.group]
        if joint == -1 or weight == 0:
            return
        joints.append(joint)
        weights.append(weight)

    list(map(get_vg_info, vertex.groups))
    return [joints, weights]


# Todo: too slow (it will take 75% of runtime)
def get_weights(mesh, bone_names):
    """Get skinning data from a mesh.

    Args:
        mesh (bpy.types.Mesh): A mesh
        bone_names (list[string]): bone names

    Returens:
        vertex_groups (list[int]): used bone ids for bone_names
        joints (list[list[int]]): ids for vertex_groups
        weights (list[list[float]]): bone weights
        max_influence_count (int): max number of joints a vertex has
    """
    mesh_data = mesh.data
    mesh_vgs = mesh.vertex_groups

    def get_index(elem, array):
        if elem in array:
            return array.index(elem)
        else:
            return -1
    vg_id_to_bone_id = [get_index(vg.name, bone_names) for vg in mesh_vgs]
    influences = [get_vertex_weight(v, vg_id_to_bone_id) for v in mesh_data.vertices]
    joints = [i[0] for i in influences]
    weights = [i[1] for i in influences]
    vertex_groups = list(set(sum(joints, [])))
    joints = [[vertex_groups.index(j) for j in joint] for joint in joints]
    max_influence_count = max([len(j) for j in joints])
    return vertex_groups, joints, weights, max_influence_count


def add_armature(name='Armature', location=(0, 0, 0)):
    """Add an armature to scene.

    Args:
        name (string): name for armature
        location (list[float]): location for armature

    Returns:
        amt (bpy.types.Armature): added armature
    """
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


def add_bone(amt, name, head, tail, z_axis_tail, parent=None):
    """Add a bone to an armature.

    Args:
        amt (bpy.types.Armature): target armature
        name (string): bone name
        head (list[float]): x,y,z for bone head
        tail (list[float]): x,y,z for bone tail
        z_axis_tail (list[float]): head->z_axis_tail will be z axis for the bone
        parent (bpy.types.EditBone): parent bone

    Returns:
        bone (bpy.types.EditBone): added bone
    """
    bone = amt.data.edit_bones.new(name)
    bone.use_deform = True
    bone.head = head
    bone.tail = tail
    z_axis = z_axis_tail - head
    bone.align_roll(z_axis)
    if parent is not None:
        bone.parent = parent
    return bone


def add_empty_mesh(amt, name, collection=None):
    """Add an empty mesh to an armature.

    Args:
        amt (bpy.types.Armature): target armature
        name (string): mesh name
        collection (bpy.types.Collection): collection the mesh will be linked

    Returns:
        obj (bpy.types.Mesh): added mesh
    """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.rotation_mode = 'QUATERNION'
    obj.show_name = True
    if collection is None:
        collection = bpy.context.scene.collection
    collection.objects.link(obj)
    if amt is not None:
        obj.parent = amt
    matrix = obj.matrix_world.copy()
    obj.matrix_local @= matrix
    return obj


def construct_mesh(mesh_data, positions, indices, uv_maps):
    """Assign mesh data to an empty mesh.

    Args:
        mesh_data ((bpy.types.Mesh).data): an empty mesh data
        positions (numpy.ndarray): 2d numpy array for vertex positions (vertex_count, 3)
        indices (numpy.ndarray): 1d numpy array for triangle indices (face_count*3)
        uv_maps (numpy.ndarray): 3d numpy array for uv maps (uv_count, vertex_count, 2)

    Returens:
        mesh_data ((bpy.types.Mesh).data): constructed mesh data
    """
    face_num = len(indices) // 3

    mesh_data.vertices.add(len(positions))
    mesh_data.vertices.foreach_set('co', positions.flatten())

    mesh_data.loops.add(len(indices))
    mesh_data.loops.foreach_set('vertex_index', indices)

    mesh_data.polygons.add(face_num)
    loop_starts = np.arange(0, 3 * face_num, step=3)
    loop_totals = np.full(face_num, 3)
    mesh_data.polygons.foreach_set('loop_start', loop_starts)
    mesh_data.polygons.foreach_set('loop_total', loop_totals)

    for uv_map, i in zip(uv_maps, range(len(uv_maps))):
        name = f'UVMap{i}'
        layer = mesh_data.uv_layers.new(name=name)
        uv_map = uv_map[indices]
        layer.data.foreach_set('uv', uv_map.flatten())
    return mesh_data


def assign_vg(vertex_id, vertex_groups, j, w):
    """Assign weights to a vertex."""
    if w > 0:
        vertex_groups[j].add([vertex_id], w, 'REPLACE')


def skinning(mesh, vg_names, joints, weights):
    """Assign weights to a mesh.

    Args:
        mesh (bpy.types.Mesh): target mesh
        vg_names (list[string]): vertex group names
        joints (numpy.ndarray): 2d numpy array of vertex group ids (vertex_count, max_influences)
        weights (numpy.ndarray): 2d numpy array of weights (vertex_count, max_influence_count)
    """
    list(map(lambda name: mesh.vertex_groups.new(name=name), vg_names))
    vgs = list(mesh.vertex_groups)
    for vertex_id, joint, weight in zip(range(len(joints)), joints, weights):
        list(map(lambda j, w: assign_vg(vertex_id, vgs, j, w), joint, weight))


def join_meshes(meshes):
    """Join meshes into a mesh.

    Args:
        meshes (list[bpy.types.Mesh]): target meshes

    Returns:
        mesh: joined mesh
    """
    # deselect_all()  # need this?
    if len(meshes) == 0:
        return None
    if len(meshes) == 1:
        return meshes[0]
    mesh_data_list = [mesh.data for mesh in meshes[1:]]

    if (3, 2, 0) > bpy.app.version:
        # Deprecated in the latest version
        ctx = bpy.context.copy()
        ctx['active_object'] = meshes[0]
        ctx['selected_editable_objects'] = meshes
        bpy.ops.object.join(ctx)
    else:
        # New API from 3.2
        with bpy.context.temp_override(active_object=meshes[0],
                                       selected_editable_objects=meshes):
            bpy.ops.object.join()

    # remove unnecessary mesh data
    deselect_all()
    for mesh_data in mesh_data_list:
        bpy.data.meshes.remove(mesh_data)
    return meshes[0]


def smoothing(mesh_data, face_count, normals, enable_smoothing=True):
    """Imoprt vertex normals and apply sooth shading.

    Args:
        mesh_data ((bpy.types.Mesh).data): target mesh
        face_count (int): number of faces
        normals (numpy.ndarray): 2d numpy array of normals (vertex_count, 3)
        enable_smoothing (bool): apply smooth shading or not
    """
    smooth = np.empty(face_count, dtype=bool)
    smooth.fill(enable_smoothing)
    mesh_data.polygons.foreach_set('use_smooth', smooth)
    mesh_data.validate()
    mesh_data.update()
    mesh_data.create_normals_split()
    mesh_data.normals_split_custom_set_from_vertices(normals)
    mesh_data.use_auto_smooth = enable_smoothing


def hsv_to_rgb(hue, sat, val):
    """Color space converter between HSV and RGB."""
    hue_i = int(hue * 6)
    hue_f = hue * 6 - hue_i
    n_1 = val * (1 - sat)
    n_2 = val * (1 - hue_f * sat)
    n_3 = val * (1 - (1 - hue_f) * sat)
    if hue_i == 0:
        red, green, blue = val, n_3, n_1
    elif hue_i == 1:
        red, green, blue = n_2, val, n_1
    elif hue_i == 2:
        red, green, blue = n_1, val, n_3
    elif hue_i == 3:
        red, green, blue = n_1, n_2, val
    elif hue_i == 4:
        red, green, blue = n_3, n_1, val
    elif hue_i == 5:
        red, green, blue = val, n_1, n_2
    return [red, green, blue]


class ColorGenerator:
    """Color generator for materials.

    Notes:
        https://martin.ankerl.com/2009/12/09/how-to-create-random-colors-programmatically/
    """

    def __init__(self):
        """Constructor."""
        self.hue = 0

    golden_ratio_conjugate = 0.618033988749895

    def gen_new_color(self):
        """Generate new color."""
        self.hue += ColorGenerator.golden_ratio_conjugate
        self.hue %= 1
        red, green, blue = hsv_to_rgb(self.hue, 0.5, 0.95)
        return (red, green, blue, 1)


def add_material(name, color_gen=None):
    """Add a new material to scene."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    if color_gen is not None:
        material.diffuse_color = color_gen.gen_new_color()
    nodes = material.node_tree.nodes
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Specular'].default_value = 0.0
    material.use_backface_culling = True
    return material


def enable_alpha_for_material(material):
    """Allow a mateiral to use alpha textures."""
    material.blend_method = 'HASHED'
    material.shadow_method = 'HASHED'


def load_tga(file, name, color_space='Non-Color'):
    """Load tga file.

    Args:
        file (string): file path for dds
        name (string): object name for the texture
        color_space (string): color space

    Returns:
        tex (bpy.types.Image): loaded texture
    """
    tex = bpy.data.images.load(file)
    tex.pack()
    tex.colorspace_settings.name = color_space
    tex.filepath = ''
    tex.filepath_raw = ''
    tex.name = name
    return tex


def load_dds(file, name, tex_type='COLOR',
             color_space='Non-Color', invert_normals=False):
    """Load dds file.

    Args:
        file (string): file path for dds
        name (string): object name for the texture
        tex_type (string): texture type ('COLOR' or 'NORMAL' or 'GLAY')
        color_space (string): color space
        invert_normals (bool): Flip y axis if the texture type is 'NORMAL'.

    Returns:
        tex (bpy.types.Image): loaded texture
    """
    tex = bpy.data.images.load(file)
    tex.pack()
    tex.colorspace_settings.name = color_space
    tex.filepath = ''
    tex.filepath_raw = ''

    tex.name = name

    if tex_type == 'NORMAL':
        # reconstruct z (x*x+y*y+z*z=1)
        print('Reconstructing normal map...')
        pix = np.array(tex.pixels, dtype=np.float32)
        pix = pix.reshape((-1, 4))
        pix_xy = pix[:, [0, 1]] * 2 - 1  # (0~1)->(-1~1)
        squared = np.square(pix_xy)
        z = np.sqrt(np.clip(1 - squared[:, 0] - squared[:, 1], 0, None))
        pix[:, 2] = (z + 1) * 0.5  # (-1~1)->(0~1)
        if invert_normals:
            pix[:, 1] = 1 - pix[:, 1]
        pix = pix.flatten()
        tex.pixels = pix

    elif tex_type == 'GRAY':
        print('Reconstructing gray scale map...')
        # copy r to g and b
        pix = np.array(tex.pixels)
        pix = pix.reshape((-1, 4))
        pix[:, [1, 2]] = pix[:, [0, 0]]
        pix = pix.flatten()
        tex.pixels = pix
    return tex


def assign_texture(texture, material, tex_type='COLOR',
                   location=(-800, 300), invert_normals=True):
    """Make shader nodes for a texture and a material.

    Args:
        texture (bpy.types.Image): target texture
        material (bpy.types.Material): target material
        tex_type (string): texture type
        location (list[int]): location for the texture in shader nodes graph
        invert_normals (bool): Flip y axis if the texture type is NORMAL

    Notes:
        Texture types
        - COLOR: 3ch map.
        - COLOR_MAIN: 3ch map. This will be connected to shader as a main color map.
        - NORMAL: 2ch map.
        - NORMAL_MAIN: 2ch map. This will be connected to shader as a main normal map.
        - GLAY: 1ch map.
        - ALPHA: 1ch map. This will be connected to shader as a main alpha texture
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    bsdf_node = nodes.get('Principled BSDF')
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = texture
    tex_node.location = location

    if tex_type == 'COLOR_MAIN':
        links.new(bsdf_node.inputs['Base Color'], tex_node.outputs['Color'])
        tex_node.image.colorspace_settings.name = 'sRGB'
    if 'NORMAL' in tex_type:
        normal_node = nodes.new('ShaderNodeNormalMap')
        if invert_normals:
            curve_node = nodes.new('ShaderNodeRGBCurve')
            curve_node.location = [location[0] + 300, location[1]]
            curve_node.mapping.curves[1].points[0].location = (0, 1)
            curve_node.mapping.curves[1].points[1].location = (1, 0)
            curve_node.mapping.update()
            normal_node.location = [location[0] + 600, location[1]]
            links.new(curve_node.inputs['Color'], tex_node.outputs['Color'])
            links.new(normal_node.inputs['Color'], curve_node.outputs['Color'])
        else:
            normal_node.location = [location[0] + 450, location[1]]
            links.new(normal_node.inputs['Color'], tex_node.outputs['Color'])
        if 'MAIN' in tex_type:
            links.new(bsdf_node.inputs['Normal'], normal_node.outputs['Normal'])
    if 'ALPHA' in tex_type:
        links.new(bsdf_node.inputs['Alpha'], tex_node.outputs['Color'])
        enable_alpha_for_material(material)


def make_trs(trans, rot, scale):
    """Calculate TRS matrix.

    Args:
        trans (mathutil.Vector): x,y,z for locatoin
        rot (mathutil.Quaternion): w,x,y,z for rotation
        scale (mathutil.Vector): x,y,z for scale

    Returns:
        trs (mathutil.Matrix): TRS matrix

    Notes:
        Same as Matrix.LocRotScale. but 2.8x doesn't support it.
    """
    if (3, 0, 0) > bpy.app.version:
        mat_trans = Matrix.Translation(trans)
        mat_rot = rot.to_matrix().to_4x4()
        mat_sca = Matrix.Diagonal(scale).to_4x4()
        return mat_trans @ mat_rot @ mat_sca
    else:
        return Matrix.LocRotScale(trans, rot, scale)


def get_animation_data(amt, start_frame=0, num_samples=1, interval=1):
    """Get animation data as a dictionary.

    Args:
        amt (bpy.types.Armature): target armature
        start_frame (float): start frame for the animation
        num_samples (int): number of frames
        interval (float): duration time for each frame

    Returns:
        anim_data (dict): animation data

    Notes:
        anim_data[bone_name][element] = [vec_for_frame0, vec_for_frame1, ...]
        element: 'location', 'scale', 'rotation_quaternion' or 'rotation_euler'
    """
    fcurves = amt.animation_data.action.fcurves
    anim_data = {}
    for fc in fcurves:
        idx = fc.array_index
        data_path = fc.data_path.split('.')
        if len(data_path) != 3 or data_path[0] != 'pose':
            continue

        num_key_frames = len(fc.keyframe_points)
        if num_key_frames == 0:
            continue
        bone_name = data_path[1].split('"')[1]
        data_type = data_path[2]
        if data_type not in ['location', 'scale', 'rotation_quaternion', 'rotation_euler']:
            continue
        if bone_name not in anim_data:
            bone_anim_data = {}
            anim_data[bone_name] = bone_anim_data
        else:
            bone_anim_data = anim_data[bone_name]
        if data_type not in bone_anim_data:
            elem_anim_data = [[] for i in range(3 + (data_type == 'rotation_quaternion'))]
            bone_anim_data[data_type] = elem_anim_data
        else:
            elem_anim_data = bone_anim_data[data_type]
        if num_key_frames == 1:
            points = [fc.evaluate(0)]
        else:
            points = [fc.evaluate(start_frame + t * interval) for t in range(num_samples)]
        elem_anim_data[idx] = points

    for bone_anim in anim_data.values():
        for data_type, elem_anim in bone_anim.items():
            frame_count = max([len(points) for points in elem_anim])
            for points, idx in zip(elem_anim, range(len(elem_anim))):
                if len(points) == 1:
                    points = points * frame_count
                elif len(points) == 0:
                    if (len(elem_anim) == 4 and idx == 0) or data_type == 'scale':
                        points = [1] * frame_count
                    else:
                        points = [0] * frame_count
            bone_anim[data_type] = [[points[t] for points in elem_anim] for t in range(frame_count)]

    return anim_data
