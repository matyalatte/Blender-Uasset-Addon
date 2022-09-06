"""Class for .uexp file."""

import os

from ..util import io_util as io
from ..util import cipher
from .mesh import StaticMesh, SkeletalMesh
from .skeleton import SkeletonAsset
from .texture import Texture
from .animation import AnimSequence


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
            raise RuntimeError(f'Not .uexp! ({file})')
        if not os.path.exists(file):
            msg = 'FileNotFound: You should put .uexp in the same directory as .uasset.'
            raise RuntimeError(msg + f'({file})')

        # get name list and export data from .uasset
        self.uasset = uasset
        self.name_list = self.uasset.name_list
        self.exports = self.uasset.exports
        self.imports = self.uasset.imports
        self.asset_path = self.uasset.asset_path

        self.version = self.uasset.version
        self.asset_type = self.uasset.asset_type

        if verbose:
            print(f'Asset type: {self.asset_type}')
        # print('Loading '+file+'...', ignore_verbose=True)
        # open .uexp
        self.mesh = None
        self.skeleton = None
        with open(file, 'rb') as f:
            for export in self.exports:
                if f.tell() + self.uasset.size != export.offset:
                    raise RuntimeError('Parse failed.')

                if verbose:
                    print(f'{export.name} (offset: {f.tell()})')
                    print(f'  size: {export.size}')
                if export.ignore:
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
                    elif self.asset_type == 'AnimSequence':
                        self.anim = AnimSequence.read(f, self.uasset, verbose=verbose)
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
                    if self.asset_type in ['SkeletalMesh', 'StaticMesh']:
                        self.mesh.write(f)
                    elif self.asset_type == 'Skeleton':
                        self.skeleton.write(f)
                    elif 'Texture' in self.asset_type:
                        self.texture.write(f)
                    elif self.asset_type == 'AnimSequence':
                        self.anim.write(f)
                    else:
                        raise RuntimeError(f'Unsupported asset. ({self.asset_type})')
                    f.write(self.unknown2)
                    size = f.tell() - offset

                export.update(size, offset)

            f.write(self.meta)
            f.write(self.foot)
            uexp_size = f.tell()
        return uexp_size

    def import_from_blender(self, primitives, only_mesh=True):
        """Import asset data from Blender."""
        if self.skeleton is None and self.mesh is None:
            raise RuntimeError(f'Injection is not supported for {self.asset_type}')
        if self.mesh is None and only_mesh:
            raise RuntimeError(f"Enabled 'Only Mesh' option, but the asset have no meshes. ({self.asset_type}")
        if not only_mesh and self.skeleton is not None:
            self.skeleton.import_bones(primitives['BONES'], self.name_list)
        if self.mesh is not None:
            self.mesh.import_from_blender(primitives, self.uasset, only_mesh=only_mesh)

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
