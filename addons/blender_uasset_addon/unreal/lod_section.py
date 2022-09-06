"""Classes for LOD sections."""
from ..util import io_util as io


class LODSection:
    """Base class for LOD sections."""
    def __init__(self):
        """Constructor."""
        self.material_id = None

    def update_material_ids(self, new_material_ids):
        """Reorder material ids."""
        self.material_id = new_material_ids[self.material_id]


class StaticLODSection(LODSection):
    """LOD section for static mesh."""
    def __init__(self, f, version):
        """Read function."""
        self.version = version
        self.material_id = io.read_uint32(f)
        self.first_ib_id = io.read_uint32(f)
        self.face_num = io.read_uint32(f)
        self.first_vertex_id = io.read_uint32(f)
        self.last_vertex_id = io.read_uint32(f)
        self.enable_collision = io.read_uint32(f)
        self.cast_shadow = io.read_uint32(f)
        if version >= '4.27':
            self.unk = io.read_uint32(f)  # ForceOpaque?
            self.unk2 = io.read_uint32(f)  # VisibleInRayTracing?

    @staticmethod
    def read(f, version):
        """Read function."""
        return StaticLODSection(f, version)

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.material_id)
        io.write_uint32(f, self.first_ib_id)
        io.write_uint32(f, self.face_num)
        io.write_uint32(f, self.first_vertex_id)
        io.write_uint32(f, self.last_vertex_id)
        io.write_uint32(f, self.enable_collision)
        io.write_uint32(f, self.cast_shadow)
        if self.version >= '4.27':
            io.write_uint32(f, self.unk)
            io.write_uint32(f, self.unk2)

    def print(self, i, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'section{i}')
        print(pad + f'  material_id: {self.material_id}')
        print(pad + f'  first_ib_id: {self.first_ib_id}')
        print(pad + f'  face_num: {self.face_num}')
        print(pad + f'  first_vertex_id: {self.first_vertex_id}')
        print(pad + f'  last_vertex_id: {self.last_vertex_id}')
        print(pad + f'  enable_collision: {self.enable_collision > 0}')
        print(pad + f'  cast_shadow: {self.cast_shadow > 0}')

    def import_from_blender(self, material_id, first_vertex_id, vert_num, first_ib_id, face_num):
        """Import section data from Blender."""
        self.material_id = material_id
        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.first_vertex_id = first_vertex_id
        self.last_vertex_id = first_vertex_id + vert_num - 1


class SkeletalLODSection(LODSection):
    """Base class for skeletal LOD section."""
    def remove_KDI(self):
        """Disable KDI."""
        self.unk1 = 0
        self.unk2 = []

    @staticmethod
    def bone_ids_to_name(bone_ids, bones):
        """Convert bone ids to bone names."""
        bone_name_list = [bones[id].name for id in bone_ids]
        return bone_name_list


class SkeletalLODSection4(SkeletalLODSection):
    """LOD section of skeletal mesh for old UE versions.

    Notes:
        There is .ubulk for UE5 static mesh but maybe no need it.
    """
    # material_id: material id
    # first_ib_id: Where this section start in face data.
    # face_num: the number of faces in this section
    # first_vertex_id: Where this section start in vertex data.
    # vertex_group: Id of weight painted bones. Bone influences are specified by vertex_group's id (not bone id).
    # vertex_num: the number of vertices in this section
    CorrespondClothAssetIndex = b'\xCD\xCD'

    def __init__(self, version, material_id, first_ib_id, face_num, unk,
                 recompute_tangent, cast_shadow,
                 first_vertex_id, vertex_group, vertex_num, max_bone_influences,
                 unk1, unk2):
        """Constructor."""
        self.version = version
        self.material_id = material_id
        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.unk = unk
        self.recompute_tangent = recompute_tangent
        self.cast_shadow = cast_shadow
        self.first_vertex_id = first_vertex_id
        self.vertex_group = vertex_group
        self.vertex_num = vertex_num
        self.max_bone_influences = max_bone_influences
        self.unk1 = unk1
        self.unk2 = unk2

    @staticmethod
    def read(f, version):
        """Read function."""
        io.check(io.read_uint16(f), 1, f)
        material_id = io.read_uint16(f)
        first_ib_id = io.read_uint32(f)
        face_num = io.read_uint32(f)
        io.read_null(f)
        io.check(f.read(3), b'\x00\xff\xff')
        unk = f.read(1)
        recompute_tangent = io.read_uint32(f)
        cast_shadow = io.read_uint32(f)
        first_vertex_id = io.read_uint32(f)

        vertex_group = io.read_uint16_array(f)

        vertex_num = io.read_uint32(f)

        max_bone_influences = io.read_uint32(f)

        io.read_null_array(f, 3)
        cloth_asset_index = f.read(2)
        io.check(cloth_asset_index, SkeletalLODSection4.CorrespondClothAssetIndex, f,
                 'Parse failed! (LOD_Section:CorrespondClothAssetIndex)')
        io.read_null_array(f, 4, 'LOD_Section:ClothingSectionData: GUID should be null.')
        unknown = io.read_int32(f)
        io.check(unknown, -1, f, 'LOD_Section:ClothingSectionData: AssetLodIndex should be -1.')
        if version in ['ff7r', 'kh3']:
            unk1 = io.read_uint32(f)
            num = io.read_uint32(f)
            io.check(unk1 == 1, num > 0, f)
            unk2 = io.read_uint8_array(f, length=num * 16)
        else:
            unk1 = None
            unk2 = None
        section = SkeletalLODSection4(version, material_id, first_ib_id, face_num, unk,
                                      recompute_tangent, cast_shadow,
                                      first_vertex_id, vertex_group, vertex_num, max_bone_influences,
                                      unk1, unk2)
        return section

    def copy(self):
        """Copy itself."""
        return SkeletalLODSection4(self.version, self.material_id,
                                   self.first_ib_id, self.face_num, self.unk,
                                   self.recompute_tangent, self.cast_shadow,
                                   self.first_vertex_id, self.vertex_group,
                                   self.vertex_num, self.max_bone_influences,
                                   0, [])

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint16(f, self.material_id)
        io.write_uint32(f, self.first_ib_id)
        io.write_uint32(f, self.face_num)
        io.write_null(f)
        f.write(b'\x00\xff\xff')
        f.write(self.unk)
        io.write_uint32(f, self.recompute_tangent)
        io.write_uint32(f, self.cast_shadow)
        io.write_uint32(f, self.first_vertex_id)
        io.write_uint16_array(f, self.vertex_group, with_length=True)
        io.write_uint32(f, self.vertex_num)
        io.write_uint32(f, self.max_bone_influences)
        io.write_null_array(f, 3)
        f.write(SkeletalLODSection4.CorrespondClothAssetIndex)
        io.write_null_array(f, 4)
        io.write_int32(f, -1)
        if self.version in ['ff7r', 'kh3']:
            io.write_uint32(f, self.unk1)
            io.write_uint32(f, len(self.unk2) // 16)
            io.write_uint8_array(f, self.unk2)

    def print(self, name, bones, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + 'section ' + name)
        print(pad + f'  material_id: {self.material_id}')
        print(pad + f'  first_ib_id: {self.first_ib_id}')
        print(pad + f'  face_num: {self.face_num}')
        print(pad + f'  first_vertex_id: {self.first_vertex_id}')
        vg_name = SkeletalLODSection.bone_ids_to_name(self.vertex_group, bones)
        print(pad + f'  vertex_group: {vg_name}')
        print(pad + f'  vertex_num: {self.vertex_num}')
        print(pad + f'  max bone influences: {self.max_bone_influences}')
        if self.unk2 is not None:
            print(pad + f'  KDI flag: {self.unk1 > 0}')
            print(pad + f'  vertices influenced by KDI: {len(self.unk2) // 16}')

    def import_from_blender(self, vertex_group, material_id, first_vertex_id, vertex_num,
                            first_ib_id, face_num, max_bone_influences):
        """Import section data from Blender."""
        self.material_id = material_id
        self.vertex_group = vertex_group

        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.first_vertex_id = first_vertex_id
        self.vertex_num = vertex_num
        self.max_bone_influences = max_bone_influences


class SkeletalLODSection5(LODSection):
    """LOD section for UE5 skeletal mesh (FSkelMeshSection)."""

    def __init__(self, version, material_id, first_ib_id, face_num, unk,
                 first_vertex_id, vertex_group, vertex_num, max_bone_influences,
                 unk_ids, unk_ids2, cast_shadow, ray_tracing):
        """Constructor."""
        self.version = version
        self.material_id = material_id
        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.unk = unk
        self.first_vertex_id = first_vertex_id
        self.vertex_group = vertex_group
        self.vertex_num = vertex_num
        self.max_bone_influences = max_bone_influences
        self.unk_ids = unk_ids
        self.unk_ids2 = unk_ids2
        self.cast_shadow = cast_shadow
        self.ray_tracing = ray_tracing

    @staticmethod
    def read(f, version):
        """Read function."""
        io.check(io.read_uint16(f), 1)
        material_id = io.read_uint16(f)
        first_ib_id = io.read_uint32(f)
        face_num = io.read_uint64(f)
        unk = io.read_uint8(f)
        cast_shadow = io.read_uint32(f)
        if version >= '5.0':
            ray_tracing = io.read_uint32(f)
        else:
            ray_tracing = None
        first_vertex_id = io.read_uint64(f)
        vertex_group = io.read_uint16_array(f)
        vertex_num = io.read_uint32(f)
        max_bone_influences = io.read_uint32(f)
        io.check(f.read(2), b'\xff\xff')  # CorrespondClothAssetIndex?
        io.read_null_array(f, 4)  # AssetGuid for FClothingSectionData?
        io.check(io.read_int32(f), -1)  # AssetLodIndex for FClothingSectionData?
        unk_ids = io.read_uint32_array(f)
        io.read_const_uint32(f, vertex_num)
        unk_ids2 = f.read(vertex_num * 8)
        io.read_null(f)
        section = SkeletalLODSection5(version, material_id, first_ib_id, face_num, unk,
                                      first_vertex_id, vertex_group, vertex_num, max_bone_influences,
                                      unk_ids, unk_ids2, cast_shadow, ray_tracing)
        return section

    def copy(self):
        """Copy itself."""
        return SkeletalLODSection5(self.version, self.material_id,
                                   self.first_ib_id, self.face_num, self.unk,
                                   self.first_vertex_id, self.vertex_group, self.vertex_num,
                                   self.max_bone_influences,
                                   self.unk_ids, self.unk_ids2, self.cast_shadow, self.ray_tracing)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint16(f, self.material_id)
        io.write_uint32(f, self.first_ib_id)
        io.write_uint64(f, self.face_num)
        io.write_uint8(f, self.unk)
        io.write_uint32(f, self.cast_shadow)
        if self.version >= '5.0':
            io.write_uint32(f, self.ray_tracing)
        io.write_uint64(f, self.first_vertex_id)
        io.write_uint16_array(f, self.vertex_group, with_length=True)
        io.write_uint32(f, self.vertex_num)
        io.write_uint32(f, self.max_bone_influences)

        f.write(b'\xff\xff')
        io.write_null_array(f, 4)
        io.write_int32(f, -1)
        io.write_uint32_array(f, self.unk_ids, with_length=True)
        io.write_uint32(f, self.vertex_num)
        f.write(self.unk_ids2)
        io.write_null(f)

    def print(self, name, bones, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + 'section ' + name)
        print(pad + f'  material_id: {self.material_id}')
        print(pad + f'  first_ib_id: {self.first_ib_id}')
        print(pad + f'  face_num: {self.face_num}')
        print(pad + f'  first_vertex_id: {self.first_vertex_id}')
        vg_name = SkeletalLODSection.bone_ids_to_name(self.vertex_group, bones)
        print(pad + f'  vertex_group: {vg_name}')
        print(pad + f'  vertex_num: {self.vertex_num}')
        print(pad + f'  max bone influences: {self.max_bone_influences}')
        print(pad + f'  cast_shadow: {self.cast_shadow}')
        if self.ray_tracing is not None:
            print(pad + f'  ray_tracing: {self.ray_tracing}')

    def import_from_blender(self, vertex_group, material_id, first_vertex_id,
                            vertex_num, first_ib_id, face_num, max_bone_influences):
        """Imoprt section data from Blender."""
        self.material_id = material_id
        self.vertex_group = vertex_group

        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.first_vertex_id = first_vertex_id
        self.vertex_num = vertex_num
        self.max_bone_influences = max_bone_influences
