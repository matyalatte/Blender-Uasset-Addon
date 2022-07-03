"""Class for .uexp file."""

import os

from ..util import io_util as io
from ..util import cipher
from .mesh import StaticMesh, SkeletalMesh
from .skeleton import SkeletonAsset
from .texture import Texture


class Uexp:
    """Class for .uexp file."""

    UNREAL_SIGNATURE = b'\xC1\x83\x2A\x9E'

    def __init__(self, file, uasset, verbose=False):
        """Load .uexp."""
        self.author = ''
        self.meta = ''
        self.load(file, uasset, verbose=verbose)

    def load(self, file, uasset, verbose=False):
        """Load .uexp."""
        if file[-4:] != 'uexp':
            raise RuntimeError('Not .uexp! ({})'.format(file))
        if not os.path.exists(file):
            msg = 'FileNotFound: You should put .uexp in the same directory as .uasset.'
            raise RuntimeError(msg + '({})'.format(file))

        # get name list and export data from .uasset
        self.uasset = uasset
        self.name_list = self.uasset.name_list
        self.exports = self.uasset.exports
        self.imports = self.uasset.imports
        self.asset_path = self.uasset.asset_path

        self.version = self.uasset.version
        self.asset_type = self.uasset.asset_type

        if verbose:
            print('Asset type: {}'.format(self.asset_type))

        # check materials
        if self.asset_type in ['SkeletalMesh', 'StaticMesh']:
            has_material = False
            for imp in self.imports:
                if imp.material:
                    has_material = True
            if not has_material:
                msg = 'Material slot is empty. Be sure materials are assigned correctly in UE4.'
                raise RuntimeError(msg)

        # print('Loading '+file+'...', ignore_verbose=True)
        # open .uexp
        self.mesh = None
        self.skeleton = None
        with open(file, 'rb') as f:
            for export in self.exports:
                if f.tell() + self.uasset.size != export.offset:
                    raise RuntimeError('Parse failed.')

                if export.ignore:
                    if verbose:
                        print('{} (offset: {})'.format(export.name, f.tell()))
                        print('  size: {}'.format(export.size))
                    export.read_uexp(f)

                else:
                    # 'SkeletalMesh', 'StaticMesh', 'Skeleton'
                    if self.asset_type == 'SkeletalMesh':
                        self.mesh = SkeletalMesh.read(f, self.uasset, verbose=verbose)
                        self.skeleton = self.mesh.skeleton
                    elif self.asset_type == 'StaticMesh':
                        self.mesh = StaticMesh.read(f, self.uasset, verbose=verbose)
                    elif self.asset_type == 'Skeleton':
                        self.skeleton = SkeletonAsset.read(f, self.version, self.name_list, verbose=verbose)
                    elif 'Texture' in self.asset_type:
                        self.texture = Texture.read(f, self.uasset, verbose=verbose)
                    self.unknown2 = f.read(export.offset + export.size - f.tell() - self.uasset.size)

            offset = f.tell()
            size = io.get_size(f)
            self.meta = f.read(size - offset - 4)
            self.author = cipher.decrypt(self.meta)

            if self.author != '' and verbose:
                print(f'Author: {self.author}')
            self.foot = f.read()
            io.check(self.foot, Uexp.UNREAL_SIGNATURE, f, 'Parse failed. (foot)')

    def load_material_asset(self):
        """Load material files and store texture paths."""
        if self.mesh is not None:
            for mat in self.mesh.materials:
                mat.load_asset(self.uasset.actual_path, self.asset_path, version=self.version)

    def save(self, file):
        """Save .uexp file."""
        print('Saving ' + file + '...')
        with open(file, 'wb') as f:
            for export in self.exports:
                offset = f.tell()
                if export.ignore:
                    export.write_uexp(f)
                    size = export.size
                else:
                    if self.asset_type == 'SkeletalMesh':
                        SkeletalMesh.write(f, self.mesh)
                    elif self.asset_type == 'StaticMesh':
                        StaticMesh.write(f, self.mesh)
                    elif self.asset_type == 'Skeleton':
                        SkeletonAsset.write(f, self.skeleton)
                    elif 'Texture' in self.asset_type:
                        self.texture.write(f)
                    else:
                        raise RuntimeError('Unsupported asset. ({})'.format(self.asset_type))
                    f.write(self.unknown2)
                    size = f.tell() - offset

                export.update(size, offset)

            f.write(self.meta)
            f.write(self.foot)
            uexp_size = f.tell()
        return uexp_size

    """
    def import_LODs(self, mesh_uexp, only_mesh=False, only_phy_bones=False,
                    dont_remove_KDI=False):
        if self.asset_type != mesh_uexp.asset_type and self.asset_type != 'Skeleton':
            raise RuntimeError('Asset types are not the same. ({}, {})'.format(self.asset_type, mesh_uexp.asset_type))
        if self.asset_type == 'SkeletalMesh':
            self.mesh.import_LODs(mesh_uexp.mesh, self.imports, self.name_list, self.uasset.file_data_ids,
                                  only_mesh=only_mesh,
                                  only_phy_bones=only_phy_bones, dont_remove_KDI=dont_remove_KDI)
        elif self.asset_type == 'StaticMesh':
            self.mesh.import_LODs(mesh_uexp.mesh, self.imports, self.name_list, self.uasset.file_data_ids)
        elif self.asset_type == 'Skeleton':
            if mesh_uexp.asset_type == 'SkeletalMesh':
                self.skeleton.import_bones(mesh_uexp.mesh.skeleton.bones, self.name_list,
                                           only_phy_bones=only_phy_bones)
            elif mesh_uexp.asset_type == 'Skeleton':
                self.skeleton.import_bones(mesh_uexp.skeleton.bones, self.name_list,
                                           only_phy_bones=only_phy_bones)
            else:
                raise RuntimeError('ue4_18_file should have skeleton.')
    """

    def import_from_blender(self, primitives, only_mesh=True):
        """Import asset data from Blender."""
        if self.skeleton is None and self.mesh is None:
            raise RuntimeError('Injection is not supported for {}'.format(self.asset_type))
        if self.mesh is None and only_mesh:
            raise RuntimeError("Enabled 'Only Mesh' option, but the asset have no meshes. ({})".format(self.asset_type))
        if not only_mesh and self.skeleton is not None:
            self.skeleton.import_bones(primitives['BONES'], self.name_list)
        if self.mesh is not None:
            self.mesh.import_from_blender(primitives, self.imports, self.name_list,
                                          self.uasset.file_data_ids, only_mesh=only_mesh)

    def embed_string(self, string):
        """Embed string to .uexp."""
        self.author = string
        self.meta = cipher.encrypt(string)
        print('A string has been embedded into uexp.')
        print(f'  string: {string}')
        print(f'  size: {len(self.meta)}')

    def get_author(self):
        """Get embedded data."""
        return self.author

    def add_material_slot(self):
        """Add material slot to asset."""
        if self.asset_type != 'SkeletalMesh':
            raise RuntimeError('Unsupported feature for static mesh')
        self.mesh.add_material_slot(self.imports, self.name_list, self.uasset.file_data_ids, material=None)
        print('Added a new material slot')
