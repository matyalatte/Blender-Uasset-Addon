"""Tests for unreal/*.py

Notes:
    Need ./Matya-Uasset-Samples/database.json to get test cases.
"""
import json
import os

import pytest
import shutil

import blender_uasset_addon
from blender_uasset_addon import bpy_util
from blender_uasset_addon.util.io_util import compare
from blender_uasset_addon import unreal
from blender_uasset_addon.import_uasset import load_uasset
from blender_uasset_addon.inject_to_uasset import inject_uasset
from blender_uasset_addon.export_as_fbx import export_as_fbx

RED = '\033[31m'
GREEN = '\033[32m'


def get_test_case():
    """Get test case."""
    DATABASE_DIR = 'Matya-Uasset-Samples'
    json_file = os.path.join(DATABASE_DIR, 'database.json')
    if not os.path.exists(json_file):
        print(RED + 'Sample .uasset files not found.' + RED)
        return []
    with open(json_file, 'r', encoding='utf-8') as f:
        j = json.load(f)
    samples = j['samples']
    samples = [s for s in samples if s['class'] not in ['Material', 'PhysicsAsset']]
    print(GREEN + 'Found sample .uasset files!' + GREEN)
    return [(s['version'], os.path.join(DATABASE_DIR, s['file']), s['class']) for s in samples]


TEST_CASES = get_test_case()


@pytest.mark.parametrize('version, file, asset_type', TEST_CASES)
def test_uasset_reconstruction(version, file, asset_type):
    """Cehck if the unreal module can reconstruct .uasset files."""
    asset = unreal.uasset.Uasset(file, version=version)
    tmp = '__temp__.uasset'
    asset.save(tmp)
    result = compare(file, tmp, no_err=True)
    result = result and compare(file[:-6]+'uexp', tmp[:-6]+'uexp', no_err=True)
    os.remove(tmp)
    os.remove(tmp[:-6]+'uexp')
    ubulk = tmp[:-6]+'ubulk'
    if os.path.exists(ubulk):
        os.remove(ubulk)
    assert result


@pytest.mark.parametrize('version, file, asset_type', TEST_CASES)
def test_uasset_import(version, file, asset_type):
    """Test for import function."""
    _, asset_t = load_uasset(file, ue_version=version)
    print(asset_t)
    assert asset_t == asset_type


TEST_CASE_418 = [tc for tc in TEST_CASES if tc[0] == '4.18' and tc[2] in ['SkeletalMesh', 'StaticMesh']]


@pytest.mark.parametrize('version, file, asset_type', TEST_CASE_418)
def test_uasset_injection(version, file, asset_type):
    """Test for injection."""
    imported, asset_t = load_uasset(file, load_textures=True, ue_version=version,
                                    rotate_bones=True, keep_sections=True)
    bpy_util.deselect_all()
    imported.select_set(True)
    asset_t = inject_uasset(file, os.path.dirname(file), ue_version=version, only_mesh=False)
    shutil.rmtree(os.path.join(os.path.dirname(file), 'mod_name_here'))
    assert asset_t == asset_type


@pytest.mark.parametrize('version, file, asset_type', TEST_CASE_418)
def test_export_as_fbx(version, file, asset_type):
    """Test export function."""
    imported, asset_t = load_uasset(file, load_textures=True, invert_normal_maps=True,
                                    normalize_bones=False, ue_version=version)
    assert asset_t == asset_type
    bpy_util.deselect_all()
    imported.select_set(True)
    armature, meshes = bpy_util.get_selected_armature_and_meshes()
    fbx = file[:-6] + 'fbx'
    export_as_fbx(fbx, armature, meshes)
    assert os.path.exists(fbx)
    os.remove(fbx)


@pytest.mark.parametrize('version, file, asset_type', TEST_CASE_418)
def test_uasset_verbose(version, file, asset_type):
    """Test for verbose option."""
    asset = unreal.uasset.Uasset(file, version=version, verbose=True)
    assert asset.asset_type == asset_type


TEST_CASE_TEX = [tc for tc in TEST_CASES if tc[2] == 'Texture2D']


@pytest.mark.parametrize('version, file, asset_type', TEST_CASE_TEX)
def test_dds(version, file, asset_type):
    """Test for verbose option."""
    asset = unreal.uasset.Uasset(file, version=version)
    assert asset.asset_type == asset_type
    dds = unreal.dds.DDS.asset_to_DDS(asset)
    dds_path = file[:-6]+'dds'
    dds.save(dds_path)
    dds = unreal.dds.DDS.load(dds_path, verbose=True)
    asset.uexp.texture.inject_dds(dds)
    temp = file[:-6]+'_temp_.uasset'
    asset.save(temp)
    assert compare(file, temp, no_err=True)
    os.remove(dds_path)
    os.remove(temp)
    os.remove(temp[:-6]+'uexp')
    bulk = temp[:-6]+'ubulk'
    if os.path.exists(bulk):
        os.remove(bulk)


def test_register():
    """Test for register() and unregister()."""
    blender_uasset_addon.register()
    blender_uasset_addon.unregister()
