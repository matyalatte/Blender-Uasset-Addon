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
