"""Tests for util/*.py."""
import pytest
from blender_uasset_addon.util.version import VersionInfo
from blender_uasset_addon.util import cipher


def test_versioninfo_op():
    """Test operators of VersionInfo."""
    ver = VersionInfo('4.20', 'custom')
    assert ver == '4.20'
    assert ver == 'custom'
    assert ver == ['custom', '5']
    assert ver != '4.20.2'
    assert ver != ['4.20.2', '5']
    assert ver <= '4.20'
    assert ver <= '5.0.2'
    assert ver > '4'
    assert ver >= '4.20'
    assert ver >= '3'
    assert str(ver) == 'custom'
    assert ver.copy() == '4.20'


def test_versioninfo_eq_error():
    """Test VersionInfo.__eq__."""
    with pytest.raises(Exception) as e:
        ver = VersionInfo('4.20')
        ver == 1
    assert str(e.value) == f"Comparison method doesn't support {type(1)}."


def test_versioninfo_ne_error():
    """Test VersionInfo.__ne__."""
    with pytest.raises(Exception) as e:
        ver = VersionInfo('4.20')
        ver != 1.2
    assert str(e.value) == f"Comparison method doesn't support {type(1.2)}."


def test_versioninfo_const_error():
    """Test VersionInfo.__init__."""
    with pytest.raises(Exception) as e:
        VersionInfo('5.0.2.1')
    assert str(e.value) == 'Unsupported version info.(5.0.2.1)'


@pytest.mark.parametrize('string', ['testtesttest', '', 'oaiwjfoihgaohionn'*30])
def test_cipher(string):
    """Test chipher."""
    encrypted = cipher.encrypt(string)
    decrypted = cipher.decrypt(encrypted)
    assert string == decrypted
