import os
from ..util import io_util as io
from . import uasset


# Base class for material
class Material:
    def __init__(self, import_id, slot_name_id, bin):
        self.import_id = import_id
        self.slot_name_id = slot_name_id
        self.bin = bin

    def read(f):
        pass

    def write(f, material):
        pass

    def update_material_data(materials, name_list, imports):
        for material in materials:
            material.slot_name = name_list[material.slot_name_id]
            material_import = imports[-material.import_id - 1]
            material.import_name = material_import.name
            material.class_name = material_import.class_name
            material.asset_path = material_import.parent_name

    def print(self, padding=2):
        pad = ' ' * padding
        print(pad + self.import_name)
        print(pad + '  slot name: {}'.format(self.slot_name))
        print(pad + '  asset path: {}'.format(self.asset_path))

    def assign_materials(materials1, materials2):
        # if len(materials1)!=len(materials2):
        #     raise RuntimeError('Number of materials should be the same.')

        print('Assigning materials...')

        def get_range(num):
            return [i for i in range(num)]

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

        for i in range(len(materials2)):
            if not assigned2[i]:
                new_id = assigned1.index(False)
                assigned2[i] = True
                assigned1[new_id] = True
                new_material_ids[i] = new_id

        for i, m2 in zip(range(len(materials2)), materials2):
            m1 = materials1[new_material_ids[i]]
            m1str = m1.import_name
            if m1str != m1.slot_name:
                m1str += '({})'.format(m1.slot_name)

            m2str = m2.import_name
            print('Assigned {} to {}'.format(m2str, m1str))

        return new_material_ids

    def load_asset(self, main_file_path, main_asset_path, version):
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
                m = 'Failed to load the material asset. This is unexpected. ({})'.format(file_path)
        else:
            m = 'File not found. ({})'.format(file_path)
        if m is not None:
            print(m)
            self.texture_asset_paths = [m]
            self.texture_actual_paths = []


# material for static mesh
class StaticMaterial(Material):
    def read(f):
        f.seek(2, 1)
        import_id = io.read_int32(f)
        slot_name_id = io.read_uint32(f)
        # bin=f.read(24)
        return StaticMaterial(import_id, slot_name_id, None)

    def write(f, material):
        f.write(b'\x00\x07')
        io.write_int32(f, material.import_id)
        io.write_uint32(f, material.slot_name_id)
        f.write(material.bin)

    def copy(self):
        return StaticMaterial(self.import_id, self.slot_name_id, b''.join([self.bin]))


# material for skeletal mesh
class SkeletalMaterial(Material):
    def read(f, version):
        import_id = io.read_int32(f)
        slot_name_id = io.read_uint32(f)
        bin = f.read(28 + 4 * (version >= '4.27'))  # cast shadow, uv density?
        return SkeletalMaterial(import_id, slot_name_id, bin)

    def write(f, material):
        io.write_int32(f, material.import_id)
        io.write_uint32(f, material.slot_name_id)
        f.write(material.bin)

    def copy(self):
        return SkeletalMaterial(self.import_id, self.slot_name_id, b''.join([self.bin]))
