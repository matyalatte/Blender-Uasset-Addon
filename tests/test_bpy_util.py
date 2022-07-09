"""Tests for bpy_util."""
# Todo: Write more tests.
import os

import pytest
import bpy
from blender_uasset_addon import bpy_util


def test_set_unit_scale_meter():
    """Test set_unit_scale('METERS')."""
    bpy_util.set_unit_scale('METERS')
    assert bpy.context.scene.unit_settings.scale_length == pytest.approx(1)


def test_set_unit_scale_centi():
    """Test set_unit_scale('CENTIMETERS')."""
    bpy_util.set_unit_scale('CENTIMETERS')
    assert bpy.context.scene.unit_settings.scale_length == pytest.approx(0.01)


def test_set_unit_scale_float():
    """Test set_unit_scale(float)."""
    bpy_util.set_unit_scale(0.5)
    assert bpy.context.scene.unit_settings.scale_length == pytest.approx(0.5)


def test_set_unit_scale_none():
    """Test set_unit_scale('NONE')."""
    bpy_util.set_unit_scale(0.2)
    bpy_util.set_unit_scale('NONE')
    assert bpy.context.scene.unit_settings.scale_length == pytest.approx(0.2)


def test_os_is_windows():
    """Test os_is_windows."""
    os_is_windows = os.name == 'nt'
    assert bpy_util.os_is_windows() == os_is_windows


# Todo: Can't use bpy.ops.wm.redraw_timer with pytest...
'''
def test_update_window():
    """Just run update_window once."""
    bpy_util.update_window()
    assert True
'''


def test_move_to_object_mode_empty():
    """Test move_to_object_mode with empty scene."""
    for ob in bpy.data.objects:
        bpy.data.objects.remove(ob)
    bpy_util.move_to_object_mode()
    assert (len(bpy.data.objects) == 0) and (bpy.context.mode == 'OBJECT')


def test_move_to_object_mode_edit():
    """Test move_to_object_mode with edit mode."""
    bpy.ops.mesh.primitive_cube_add()
    mesh = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH'][0]
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy_util.move_to_object_mode()
    assert bpy.context.mode == 'OBJECT'


def test_get_selected_objects():
    """Test deselect_all."""
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.select_all(action='SELECT')
    selected = bpy_util.get_selected_objects()
    assert len(selected) == 3


def test_deselect_all():
    """Test deselect_all."""
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.object.select_all(action='SELECT')
    bpy_util.deselect_all()
    selected = bpy_util.get_selected_objects()
    assert len(selected) == 0


def test_select_objects():
    """Test select_objects."""
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.mesh.primitive_cube_add()
    meshes = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH'][:2]
    bpy_util.deselect_all()
    bpy_util.select_objects(meshes)
    selected = bpy_util.get_selected_objects()
    assert len(selected) == 2


def test_join_meshes_empty():
    """Test join_meshs with empty list."""
    meshes = bpy_util.join_meshes([])
    assert meshes is None


def test_join_meshes_one():
    """Test join_meshs with a mesh."""
    bpy.ops.mesh.primitive_cube_add()
    meshes = bpy_util.get_selected_objects()
    joined = bpy_util.join_meshes(meshes)
    assert meshes[0] == joined


def test_join_meshes_some():
    """Test join_meshs with meshes."""
    bpy.ops.mesh.primitive_cube_add()
    bpy.ops.mesh.primitive_cube_add()
    meshes = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH']
    bpy_util.join_meshes(meshes)
    meshes = [ob for ob in bpy.context.scene.objects if ob.type == 'MESH']
    assert len(meshes) == 1


def test_split_mesh():
    """Test split_mesh_by_materials."""
    color_gen = bpy_util.ColorGenerator()
    meshes = []
    for i in range(3):
        bpy.ops.mesh.primitive_cube_add()
        mesh = bpy_util.get_selected_objects()[0]
        material = bpy_util.add_material(f'mat{i}', color_gen=color_gen)
        mesh.data.materials.append(material)
        meshes.append(mesh)

    mesh = bpy_util.join_meshes(meshes)
    meshes = bpy_util.split_mesh_by_materials(mesh)
    assert len(meshes) == 3


def test_split_mesh_with_no_mat():
    """Test split_mesh_by_materials."""
    with pytest.raises(Exception) as e:
        bpy.ops.mesh.primitive_cube_add()
        mesh = bpy_util.get_selected_objects()
        bpy_util.split_mesh_by_materials(mesh[0])
    assert str(e.value) == "Mesh have no materials."
