"""Classes for materials."""

import os
from ..util import io_util as io
from . import uasset


class Material:
    """Base class for material."""
    def __init__(self, import_id, slot_name_id, unk):
        """Constructor."""
        self.import_id = import_id
        self.slot_name_id = slot_name_id
        self.unk = unk
        self.import_name = None
        self.slot_name = None
        self.asset_path = None
        self.texture_asset_paths = []
        self.texture_actual_paths = []

    @staticmethod
    def read(f, version, skeletal=False):
        """Read function."""
        import_id = io.read_int32(f)
        slot_name_id = io.read_uint32(f)
        unk = f.read(28 + 4 * (skeletal and (version >= '4.27')))  # cast shadow, uv density?
        return Material(import_id, slot_name_id, unk)

    def write(self, f):
        """Write function."""
        io.write_int32(f, self.import_id)
        io.write_uint32(f, self.slot_name_id)
        f.write(self.unk)

    @staticmethod
    def get_size(version, skeletal):
        """Get binary size of a material."""
        return 36 + 4 * (skeletal and (version >= '4.27'))

    def copy(self):
        """Copy itself."""
        return Material(self.import_id, self.slot_name_id, self.unk)

    @staticmethod
    def update_material_data(materials, name_list, imports):
        """Get meta data from .uasset files."""
        for material in materials:
            material.slot_name = name_list[material.slot_name_id]
            if material.import_id != 0:
                material_import = imports[-material.import_id - 1]
                material.import_name = material_import.name
                material.class_name = material_import.class_name
                material.asset_path = material_import.parent_name
            else:
                material.import_name = material.slot_name
                material.class_name = 'None'
                material.asset_path = 'None'

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + self.import_name)
        print(pad + f'  slot name: {self.slot_name}')
        print(pad + f'  asset path: {self.asset_path}')

    @staticmethod
    def assign_materials(materials1, materials2):
        """Assign material ids."""
        print('Assigning materials...')

        def get_range(num):
            return list(range(num))

        new_material_ids = get_range(len(materials2))

        slot_names1 = [m.slot_name for m in materials1]
        slot_names2 = [m.slot_name for m in materials2]
        assigned1 = [False] * len(materials1)
        assigned2 = [False] * len(materials2)

        def assign(names1, names2, assigned1, assigned2, new_material_ids):
            for i, name in zip(range(len(materials2)), names2):
                if assigned2[i]:
                    continue
                if name in names1:
                    new_id = names1.index(name)
                    if not assigned1[new_id]:
                        new_material_ids[i] = new_id
                        assigned2[i] = True
                        assigned1[new_id] = True
            return new_material_ids, assigned1, assigned2

        # assign to the materials have same slot names
        new_material_ids, assigned1, assigned2 = assign(slot_names1, slot_names2, assigned1,
                                                        assigned2, new_material_ids)

        names1 = [m.import_name for m in materials1]
        names2 = [m.import_name for m in materials2]
        # assign to the materials have same material names
        new_material_ids, assigned1, assigned2 = assign(names1, names2, assigned1,
                                                        assigned2, new_material_ids)

        def remove_suffix(s):
            if s[-4] == '.':
                return s[:-4]
            return s

        # Remove suffix (.xxx) from material names
        names2 = [remove_suffix(n) for n in names2]
        # compare the names again
        new_material_ids, assigned1, assigned2 = assign(names1, names2, assigned1, assigned2,
                                                        new_material_ids)

        def index_of(val, in_list):
            try:
                return in_list.index(val)
            except ValueError:
                return None

        for i in range(len(materials2)):
            if not assigned2[i]:
                assigned2[i] = True
                new_id = index_of(False, assigned1)
                if new_id is not None:
                    assigned1[new_id] = True
                else:
                    new_id = len(assigned1)
                    assigned1.append(True)
                new_material_ids[i] = new_id

        for i, mat2 in zip(range(len(materials2)), materials2):
            m2str = mat2.import_name
            if i < len(materials1):
                mat1 = materials1[new_material_ids[i]]
                m1str = mat1.import_name
                if m1str != mat1.slot_name:
                    m1str += f'({mat1.slot_name})'
                print(f'Assigned {m2str} to {m1str}')
            else:
                print(f'Added {m2str} to material slots')

        return new_material_ids

    def load_asset(self, main_file_path, main_asset_path, version):
        """Load material assets and store texture paths."""
        if self.asset_path == 'None':
            return self.asset_path

        def get_actual_path(target_asset_path):
            main_asset_dir = os.path.dirname(main_asset_path)
            rel_path = os.path.relpath(os.path.dirname(target_asset_path), start=main_asset_dir)
            base = os.path.basename(target_asset_path) + '.uasset'
            return os.path.normpath(os.path.join(os.path.dirname(main_file_path), rel_path, base))

        file_path = get_actual_path(self.asset_path)
        if os.path.exists(file_path):
            try:
                material_asset = uasset.Uasset(file_path, ignore_uexp=True, version=str(version),
                                               asset_type='Material')
                self.texture_asset_paths = [
                    imp.parent_name for imp in material_asset.imports if 'Texture' in imp.class_name
                ]
                self.texture_actual_paths = [get_actual_path(p) for p in self.texture_asset_paths]
                m = None
            except Exception:
                m = f'Failed to load the material asset. This is unexpected. ({file_path})'
        else:
            m = f'File not found. ({file_path})'
        if m is not None:
            print(m)
            self.texture_asset_paths = [m]
            self.texture_actual_paths = []
