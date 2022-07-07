"""Tests for unreal/*.py

Notes:
    Need ./Matya-Uasset-Samples/database.json to get test cases.
"""
import json
import os
import pytest
from blender_uasset_addon.util.io_util import compare
from blender_uasset_addon import unreal
from blender_uasset_addon.import_uasset import load_uasset
from blender_uasset_addon.inject_to_uasset import inject_uasset

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


TEST_CASE_418 = [tc for tc in TEST_CASES if tc[0] == '4.18' and tc[2] == 'SkeletalMesh']


@pytest.mark.parametrize('version, file, asset_type', TEST_CASE_418)
def test_uasset_injection(version, file, asset_type):
    """Test for injection."""
    imported, asset_t = load_uasset(file, load_textures=True, ue_version=version)
    from blender_uasset_addon.bpy_util import deselect_all
    deselect_all()
    imported.select_set(True)
    asset_t = inject_uasset(file, os.path.dirname(file), ue_version=version, only_mesh=False)
    assert asset_t == asset_type
