"""Classes for LOD."""

import struct
from ..util import io_util as io

from .lod_section import StaticLODSection, SkeletalLODSection4, SkeletalLODSection5
from .buffer import (PositionVertexBuffer,
                     StaticMeshVertexBuffer,
                     ColorVertexBuffer,
                     StaticIndexBuffer,
                     SkeletalMeshVertexBuffer,
                     SkeletalIndexBuffer,
                     SkinWeightVertexBuffer4,
                     SkinWeightVertexBuffer5,
                     NormalVertexBuffer,
                     UVVertexBuffer,
                     KDIBuffer)


class LOD:
    """Base class for LOD."""
    def __init__(self, vb, vb2, ib, ib2, sections, color_vb=None):
        """Constructor."""
        self.vb = vb
        self.vb2 = vb2
        self.ib = ib
        self.ib2 = ib2
        self.sections = sections
        self.color_vb = color_vb

    # Todo: Generalize this function for all LOD classes.
    def get_buffers(self):
        """Get all buffers LOD has."""
        buffers = [self.vb, self.vb2, self.ib, self.ib2]
        if self.color_vb is not None:
            buffers += [self.color_vb]
        return buffers

    def update_material_ids(self, new_material_ids):
        """Reorder material ids."""
        for section in self.sections:
            section.update_material_ids(new_material_ids)

    def get_meta_for_blender(self):
        """Get meta data for Blender."""
        material_ids = [section.material_id for section in self.sections]
        return material_ids, self.uv_num


def split_list(array, first_ids):
    """Split list by ids."""
    last_ids = first_ids[1:] + [len(array)]
    splitted = [array[first: last] for first, last in zip(first_ids, last_ids)]
    return splitted


def flatten(array):
    """Flatten a list."""
    return [x for row in array for x in row]


class StaticLOD(LOD):
    """LOD for static mesh."""
    def __init__(self, offset, version, sections, flags, vb, vb2, normal_vb, color_vb,
                 ib, ib2, reversed_ib, reversed_ib2, adjacency_ib, unk, unk2):
        """Constructor."""
        self.offset = offset
        self.version = version
        self.flags = flags
        self.uv_num = vb2.uv_num
        super().__init__(vb, vb2, ib, ib2, sections, color_vb=color_vb)
        self.normal_vb = normal_vb
        self.reversed_ib = reversed_ib
        self.reversed_ib2 = reversed_ib2
        self.adjacency_ib = adjacency_ib
        self.unk = unk
        self.unk2 = unk2
        self.face_num = 0
        for section in self.sections:
            self.face_num += section.face_num

    @staticmethod
    def read(f, version):
        """Read function."""
        offset = f.tell()
        one = io.read_uint8(f)
        io.check(one, 1, f)
        unk = io.read_uint8(f)
        sections = [StaticLODSection.read(f, version) for i in range(io.read_uint32(f))]

        flags = f.read(4 + 10 * (version >= '4.27'))
        vb = PositionVertexBuffer.read(f, name='VB0')  # xyz
        if version >= '4.27':
            io.check(io.read_uint16(f), 1)
            uv_num = io.read_uint32(f)
            _ = io.read_uint32(f)  # vertex num
            use_float32UV = io.read_uint32(f)
            io.read_null(f)  # use high precision tangent basis?
            normal_vb = NormalVertexBuffer.read(f, name='Normal_VB')
            vb2 = UVVertexBuffer.read(f, uv_num, use_float32UV, name='UV_VB')
        else:
            normal_vb = None
            vb2 = StaticMeshVertexBuffer.read(f, name='VB2')  # normals+uv_maps

        color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        ib = StaticIndexBuffer.read(f, version, name='IB')  # IndexBuffer
        reversed_ib = StaticIndexBuffer.read(f, version, name='Reversed_IB')  # ReversedIndexBuffer
        ib2 = StaticIndexBuffer.read(f, version, name='IB2')  # DepathOnlyIndexBuffer
        reversed_ib2 = StaticIndexBuffer.read(f, version, name='Reversed_IB2')  # ReversedDepthOnlyIndexBuffer
        adjacency_ib = StaticIndexBuffer.read(f, version, name='Adjacency_IB')  # AdjacencyIndexBuffer
        unk2 = f.read(24)
        return StaticLOD(offset, version, sections, flags, vb, vb2, normal_vb, color_vb, ib, ib2,
                         reversed_ib, reversed_ib2, adjacency_ib, unk, unk2)

    def write(self, f):
        """Write function."""
        io.write_uint8(f, 1)
        io.write_uint8(f, self.unk)
        io.write_array(f, self.sections, with_length=True)
        f.write(self.flags)
        self.vb.write(f)
        if self.version >= '4.27':
            io.write_uint16(f, 1)
            io.write_uint32(f, self.vb2.uv_num)
            io.write_uint32(f, self.vb.vertex_num)
            io.write_uint32(f, self.vb2.use_float32UV)
            io.write_null(f)
            self.normal_vb.write(f)
            self.vb2.write(f)
        else:
            self.vb2.write(f)

        self.color_vb.write(f)

        self.ib.write(f)
        self.reversed_ib.write(f)
        self.ib2.write(f)
        self.reversed_ib2.write(f)
        self.adjacency_ib.write(f)
        f.write(self.unk2)

    def print(self, i, padding=0):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'LOD{i} (offset: {self.offset})')
        for sec, j in zip(self.sections, range(len(self.sections))):
            sec.print(j, padding=padding + 2)
        print(pad + f'face_count: {self.face_num}')
        print(pad + f'vertex_count: {self.vb.vertex_num}')
        print(pad + f'uv_count: {self.uv_num}')
        for buf in self.get_buffers():
            buf.print(padding=padding + 2)

    def parse_buffers_for_blender(self):
        """Get mesh data for Blender."""
        pos = self.vb.parse()
        if self.version >= '4.27':
            normal = self.normal_vb.parse()
            texcoords = self.vb2.parse()
        else:
            normal, texcoords = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]

        ary = [normal, pos]
        normals, positions = [split_list(elem, first_vertex_ids) for elem in ary]

        texcoords = [split_list(tc, first_vertex_ids) for tc in texcoords]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i - first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]

        return normals, positions, texcoords, None, None, None, indices

    def import_from_blender(self, primitives):
        """Import mesh data from Blender."""
        s_num1 = len(self.sections)
        f_num1 = self.ib.size // 3
        v_num1 = self.vb.vertex_num
        uv_num1 = self.uv_num

        uv_maps = primitives['UV_MAPS']  # (sction count, uv count, vertex count, 2)
        self.uv_num = len(uv_maps)
        # pos_range = self.vb.get_range()
        positions = primitives['POSITIONS']
        self.vb.import_from_blender(positions)

        normals = primitives['NORMALS']

        material_ids = primitives['MATERIAL_IDS']
        indices = primitives['INDICES']

        if len(self.sections) < len(material_ids):
            self.sections += [self.sections[-1].copy() for i in range(len(material_ids) - len(self.sections))]
        self.sections = self.sections[:len(material_ids)]

        vertex_count = primitives['VERTEX_COUNTS']
        if self.color_vb.buf is not None:
            self.color_vb.update(sum(vertex_count))
        face_count = [len(ids) // 3 for ids in indices]
        first_vertex_id = 0
        first_ids = []
        first_ib_id = 0
        for section, index, vert_num, face_num in zip(self.sections, material_ids, vertex_count, face_count):
            first_ids.append(first_vertex_id)
            section.import_from_blender(index, first_vertex_id, vert_num, first_ib_id, face_num)
            first_vertex_id += vert_num
            first_ib_id += face_num * 3

        self.vb2.import_from_blender(normals, uv_maps, self.uv_num)
        indices = [[i + first_id for i in ids] for ids, first_id in zip(indices, first_ids)]
        indices = flatten(indices)

        self.color_vb.disable()
        self.ib.update(indices, use_uint32=self.vb.size > 65000)
        self.reversed_ib.disable()
        self.ib2.disable()
        self.reversed_ib2.disable()
        self.adjacency_ib.disable()

        s_num2 = len(self.sections)
        f_num2 = self.ib.size // 3
        v_num2 = self.vb.vertex_num
        uv_num2 = self.uv_num

        print('Updated LOD0')
        print(f'  sections: {s_num1} -> {s_num2}')
        print(f'  faces: {f_num1} -> {f_num2}')
        print(f'  vertices: {v_num1} -> {v_num2}')
        print(f'  uv maps: {uv_num1} -> {uv_num2}')


class SkeletalLOD(LOD):
    """Base class for skeletal LOD."""
    def get_buffers(self):
        """Get all buffers."""
        buffers = super().get_buffers()
        if self.KDI_buffer_size > 0:
            buffers += [self.KDI_buffer, self.KDI_VB]
        return buffers

    def print(self, name, bones, padding=0):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'LOD{name} (offset: {self.offset})')
        for sec, i in zip(self.sections, range(len(self.sections))):
            sec.print(str(i), bones, padding=padding + 2)
        pad += ' ' * padding
        print(pad + f'face count: {self.ib.size // 3}')
        print(pad + f'vertex count: {self.vb.vertex_num}')
        print(pad + f'uv count: {self.uv_num}')
        for buf in self.get_buffers():
            if buf is not None:
                buf.print(padding=padding + 2)


class SkeletalLOD4(SkeletalLOD):
    """Skeketal LOD for old UE versions."""
    # sections: mesh data is separeted into some sections.
    #               each section has material id and vertex group.
    # active_bone_ids: maybe bone ids. but I don't know how it works.
    # bone_ids: active bone ids?
    # uv_num: the number of uv maps

    @staticmethod
    def read(f, version):
        """Read function."""
        return SkeletalLOD4(f, version)

    def __init__(self, f, version):
        """Read function."""
        self.offset = f.tell()
        self.version = version
        one = io.read_uint8(f)
        io.check(one, 1, f, 'Parse failed! (LOD:one)')
        no_tessellation = io.read_uint8(f)
        self.sections = [SkeletalLODSection4.read(f, self.version) for i in range(io.read_uint32(f))]

        self.KDI_buffer_size = 0
        for section in self.sections:
            if section.unk2 is not None:
                self.KDI_buffer_size += len(section.unk2) // 16

        self.ib = SkeletalIndexBuffer.read(f, name='IB')

        num = io.read_uint32(f)
        self.active_bone_ids = f.read(num * 2)

        io.read_null(f, 'Parse failed! (LOD:null1)')

        _ = io.read_uint32(f)  # vertex num

        num = io.read_uint32(f)
        self.required_bone_ids = f.read(num * 2)

        self.vertex_map = io.read_uint32_array(f)
        self.max_vertex_map_id = io.read_uint32(f)

        self.uv_num = io.read_uint32(f)
        self.vb = SkeletalMeshVertexBuffer.read(f, name='VB0')
        io.check(self.uv_num, self.vb.uv_num)
        self.vb2 = SkinWeightVertexBuffer4.read(f, name='VB2')
        test = io.read_uint8(f)
        f.seek(-1, 1)
        if test == 1 and not no_tessellation:  # HasVertexColors
            self.color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            self.color_vb = None

        if not no_tessellation:
            self.ib2 = SkeletalIndexBuffer.read(f, name='IB2')
        else:
            self.ib2 = None

        if self.KDI_buffer_size > 0:
            self.KDI_buffer = KDIBuffer.read(f, name='KDI_buffer')
            io.check(self.KDI_buffer.size, self.KDI_buffer_size, f)
            self.KDI_VB = KDIBuffer.read(f, name='KDI_VB')

    def write(self, f):
        """Write function."""
        io.write_uint8(f, 1)
        io.write_uint8(f, self.ib2 is None)
        io.write_array(f, self.sections, with_length=True)
        self.ib.write(f)
        io.write_uint32(f, len(self.active_bone_ids) // 2)
        f.write(self.active_bone_ids)
        io.write_null(f)
        io.write_uint32(f, self.vb.vertex_num)
        io.write_uint32(f, len(self.required_bone_ids) // 2)
        f.write(self.required_bone_ids)

        io.write_uint32_array(f, self.vertex_map, with_length=True)
        io.write_uint32(f, self.max_vertex_map_id)

        io.write_uint32(f, self.uv_num)
        self.vb.write(f)
        self.vb2.write(f)

        if self.color_vb is not None:
            self.color_vb.write(f)

        if self.ib2 is not None:
            self.ib2.write(f)

        if self.KDI_buffer_size > 0:
            self.KDI_buffer.write(f)
            self.KDI_VB.write(f)

    def remove_KDI(self):
        """Disable KDI."""
        self.KDI_buffer_size = 0
        self.KDI_buffer = None
        self.KDI_VB = None
        for section in self.sections:
            section.remove_KDI()

    def parse_buffers_for_blender(self):
        """Get mesh data for Blender."""
        normal, pos, texcoords = self.vb.parse()
        joint, weight = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]
        vertex_groups = [section.vertex_group for section in self.sections]

        ary = [normal, pos, joint, weight]
        normals, positions, joints, weights = [split_list(elem, first_vertex_ids) for elem in ary]

        texcoords = [split_list(tc, first_vertex_ids) for tc in texcoords]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i - first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        return normals, positions, texcoords, vertex_groups, joints, weights, indices

    def import_from_blender(self, primitives):
        """Import mesh data from Blender."""
        s_num1 = len(self.sections)
        f_num1 = self.ib.size // 3
        v_num1 = self.vb.vertex_num
        uv_num1 = self.uv_num

        bone_ids = [i for i in range(len(primitives['BONES']))]
        bone_ids = struct.pack('<' + 'H' * len(bone_ids), *bone_ids)
        self.active_bone_ids = bone_ids
        self.required_bone_ids = bone_ids
        uv_maps = primitives['UV_MAPS']  # (sction count, uv count, vertex count, 2)
        self.uv_num = len(uv_maps)
        positions = primitives['POSITIONS']
        normals = primitives['NORMALS']
        self.vb.import_from_blender(normals, positions, uv_maps, self.uv_num)
        vertex_count = primitives['VERTEX_COUNTS']
        if self.color_vb is not None:
            self.color_vb.update(sum(vertex_count))
        vertex_groups = primitives['VERTEX_GROUPS']
        material_ids = primitives['MATERIAL_IDS']
        joints = primitives['JOINTS']
        weights = primitives['WEIGHTS']
        indices = primitives['INDICES']

        if len(self.sections) < len(material_ids):
            self.sections += [self.sections[-1].copy() for i in range(len(material_ids) - len(self.sections))]
        self.sections = self.sections[:len(material_ids)]

        max_bone_influences = len(joints[0])
        face_count = [len(ids) // 3 for ids in indices]
        first_vertex_id = 0
        first_ids = []
        first_ib_id = 0
        for section, vg, index, vert_num, face_num in zip(self.sections, vertex_groups, material_ids,
                                                          vertex_count, face_count):
            first_ids.append(first_vertex_id)
            section.import_from_blender(vg, index, first_vertex_id, vert_num,
                                        first_ib_id, face_num, max_bone_influences)
            first_vertex_id += vert_num
            first_ib_id += face_num * 3

        self.vb2.import_from_blender(joints, weights, max_bone_influences > 4)
        self.color_vb = None

        indices = [[i + first_id for i in ids] for ids, first_id in zip(indices, first_ids)]
        indices = flatten(indices)

        self.ib.update(indices, ((self.vb.size > 65000) + 1) * 2)
        self.ib2 = None
        self.remove_KDI()

        s_num2 = len(self.sections)
        f_num2 = self.ib.size // 3
        v_num2 = self.vb.vertex_num
        uv_num2 = self.uv_num

        print('Updated LOD0')
        print(f'  sections: {s_num1} -> {s_num2}')
        print(f'  faces: {f_num1} -> {f_num2}')
        print(f'  vertices: {v_num1} -> {v_num2}')
        print(f'  uv maps: {uv_num1} -> {uv_num2}')


class SkeletalLOD5(SkeletalLOD):
    """Skeletal LOD for UE5."""

    @staticmethod
    def read(f, version):
        """Read function."""
        return SkeletalLOD5(f, version)

    def __init__(self, f, version):
        """Read function."""
        self.offset = f.tell()
        self.version = version
        one = io.read_uint16(f)
        io.check(one, 1, f, 'Parse failed! (LOD:one)')
        io.read_const_uint32(f, 0)
        io.read_const_uint32(f, 1)
        self.active_bone_ids = io.read_uint16_array(f)
        self.sections = [SkeletalLODSection5.read(f, self.version) for i in range(io.read_uint32(f))]
        self.required_bone_ids = io.read_uint16_array(f)
        buffer_block_size = io.read_uint32(f)
        buffer_block_start_offset = f.tell()

        io.check(io.read_uint16(f), 1)
        self.ib = SkeletalIndexBuffer.read(f, name='IB')
        self.vb = PositionVertexBuffer.read(f, name='Position_VB')
        io.check(io.read_uint16(f), 1)
        self.uv_num = io.read_uint32(f)
        _ = io.read_uint32(f)  # vertex num
        use_float32UV = io.read_uint32(f)
        io.read_null(f)  # use high precision tangent basis?

        self.normal_vb = NormalVertexBuffer.read(f, name='Normal_VB')
        self.uv_vb = UVVertexBuffer.read(f, self.uv_num, use_float32UV, name='UV_VB')

        self.weight_vb = SkinWeightVertexBuffer5.read(f, name='Weight_VB')
        io.check(io.read_uint16(f), 1)
        io.read_null(f)
        io.read_const_uint32(f, 4)
        if version >= '5.0':
            io.read_null_array(f, 4)
        else:
            io.read_null(f)
            self.adjacency_vb = SkeletalIndexBuffer.read(f, name='Adjacency_VB')
            io.read_null(f)
            io.read_null(f)
        io.check(f.tell() - buffer_block_start_offset, buffer_block_size)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint32(f, 0)
        io.write_uint32(f, 1)
        io.write_uint16_array(f, self.active_bone_ids, with_length=True)
        io.write_array(f, self.sections, with_length=True)
        io.write_uint16_array(f, self.required_bone_ids, with_length=True)
        f.seek(4, 1)
        buffer_block_start_offset = f.tell()
        io.write_uint16(f, 1)
        self.ib.write(f)
        self.vb.write(f)

        io.write_uint16(f, 1)
        io.write_uint32(f, self.uv_vb.uv_num)
        io.write_uint32(f, self.vb.vertex_num)
        io.write_uint32(f, self.uv_vb.use_float32UV)
        io.write_null(f)
        self.normal_vb.write(f)
        self.uv_vb.write(f)
        self.weight_vb.write(f)
        io.write_uint16(f, 1)
        io.write_null(f)
        io.write_uint32(f, 4)
        if self.version >= '5.0':
            io.write_null_array(f, 4)
        else:
            io.write_null(f)
            self.adjacency_vb.write(f)
            io.write_null(f)
            io.write_null(f)

        end_offset = f.tell()
        buffer_block_size = end_offset - buffer_block_start_offset
        f.seek(buffer_block_start_offset - 4)
        io.write_uint32(f, buffer_block_size)
        f.seek(end_offset)

    def get_buffers(self):
        """Get all buffers."""
        buffers = [self.ib, self.vb, self.normal_vb, self.uv_vb, self.weight_vb]
        return buffers

    def parse_buffers_for_blender(self):
        """Get mesh data for Blender."""
        normal = self.normal_vb.parse()
        pos = self.vb.parse()
        texcoords = self.uv_vb.parse()

        joint, weight = self.weight_vb.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]
        vertex_groups = [section.vertex_group for section in self.sections]

        ary = [normal, pos, joint, weight]
        normals, positions, joints, weights = [split_list(elem, first_vertex_ids) for elem in ary]
        texcoords = [split_list(tc, first_vertex_ids) for tc in texcoords]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i - first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        return normals, positions, texcoords, vertex_groups, joints, weights, indices
