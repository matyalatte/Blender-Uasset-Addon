"""Classes for buffers."""

import struct
from ..util import io_util as io


class Buffer:
    """Base class for buffers."""

    def __init__(self, stride, size, buf, offset, name):
        """Constructor."""
        self.stride = stride
        self.size = size
        self.buf = buf
        self.offset = offset
        self.name = name

    @staticmethod
    def read(f, name=''):
        """Read function."""
        stride = io.read_uint32(f)
        size = io.read_uint32(f)
        offset = f.tell()
        buf = f.read(stride * size)
        return Buffer(stride, size, buf, offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.stride)
        io.write_uint32(f, self.size)
        f.write(self.buf)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'{self.name} (offset: {self.offset})')
        _, stride, size = self.get_meta()
        print(pad + f'  stride: {stride}')
        print(pad + f'  size: {size}')

    @staticmethod
    def dump(file, buffer):
        """Write buffer."""
        with open(file, 'wb') as f:
            f.write(buffer.buf)

    def get_meta(self):
        """Get meta data."""
        return self.offset, self.stride, self.size


class VertexBuffer(Buffer):
    """Base clas for vertex buffer."""
    def __init__(self, stride, size, buf, offset, name):
        """Constructor."""
        self.vertex_num = size
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, name=''):
        """Read function."""
        buf = Buffer.read(f, name=name)
        return VertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)


class PositionVertexBuffer(VertexBuffer):
    """Positions for static mesh and UE5 skeletal mesh."""
    @staticmethod
    def read(f, name=''):
        """Read function."""
        stride = io.read_uint32(f)
        vertex_num = io.read_uint32(f)
        buf = Buffer.read(f, name=name)
        io.check(stride, buf.stride, f)
        io.check(vertex_num, buf.size, f)

        return PositionVertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.stride)
        io.write_uint32(f, self.vertex_num)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        parsed = struct.unpack('<' + 'f' * 3 * self.size, self.buf)
        position = [parsed[i * 3: i * 3 + 3] for i in range(self.size)]
        return position

    def import_from_blender(self, position):
        """Update buffer."""
        self.stride = 12
        self.size = len(position)
        self.vertex_num = self.size
        buf = flatten(position)
        self.buf = struct.pack('<' + 'f' * 3 * self.size, *buf)


class NormalVertexBuffer(VertexBuffer):
    """Normals for UE5 skeletal mesh."""
    @staticmethod
    def read(f, name=''):
        """Read function."""
        buf = Buffer.read(f, name=name)
        io.check(buf.stride, 8)
        return NormalVertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        super().write(f)

    def parse(self):
        """Parse buffer."""
        def unpack(i):
            mask8bit = 0xff
            i = i ^ 0x80808080
            x = i & mask8bit
            y = (i >> 8) & mask8bit
            z = (i >> 16) & mask8bit
            return [x, y, z]

        parsed = struct.unpack('<' + 'I' * 2 * self.size, self.buf)
        normal = [unpack(parsed[i * 2 + 1]) for i in range(self.size)]
        return normal

    def import_from_blender(self, normal):
        """Update buffer."""
        self.size = len(normal)
        self.vertex_num = self.size
        buf = normal
        buf = flatten(buf)
        self.buf = struct.pack('<' + 'B' * self.stride * self.size, *buf)


class UVVertexBuffer(VertexBuffer):
    """UV maps for UE5 skeletal mesh."""
    def __init__(self, uv_num, use_flaot32UV, stride, size, buf, offset, name):
        """Constructor."""
        self.uv_num = uv_num
        self.use_float32UV = use_flaot32UV
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, uv_num, use_float32UV, name=''):
        """Read function."""
        buf = Buffer.read(f, name=name)
        io.check(buf.stride, 4 * (1 + use_float32UV))
        return UVVertexBuffer(uv_num, use_float32UV, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        super().write(f)

    def parse(self):
        """Parse buffer."""
        float_type = 'f' if self.use_float32UV else 'e'
        parsed = struct.unpack('<' + float_type * 2 * self.size, self.buf)
        stride = 2 * self.uv_num
        size = self.size // self.uv_num
        texcoords = []
        for j in range(self.uv_num):
            texcoord = [parsed[i * stride + j * 2: i * stride + j * 2 + 2] for i in range(size)]
            texcoords.append(texcoord)
        return texcoords

    def import_from_blender(self, texcoords):
        """Update buffer."""
        self.uv_num = len(texcoords)
        size = len(texcoords[0])
        self.size = size * self.uv_num
        self.vertex_num = self.size
        buf = texcoords[0]
        if self.uv_num > 1:
            for texcoord in texcoords[1:]:
                buf = [b + t for b, t in zip(buf, texcoord)]
        buf = flatten(buf)
        float_type = 'f' if self.use_float32UV else 'e'
        self.buf = struct.pack('<' + float_type * 2 * self.size, *buf)


class StaticMeshVertexBuffer(VertexBuffer):
    """Normals and UV maps for static mesh."""
    def __init__(self, uv_num, use_float32, stride, size, buf, offset, name):
        """Constructor."""
        self.uv_num = uv_num
        self.use_float32 = use_float32
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        uv_num = io.read_uint32(f)
        stride = io.read_uint32(f)
        vertex_num = io.read_uint32(f)
        use_float32 = io.read_uint32(f)
        io.read_null(f)
        buf = Buffer.read(f, name=name)
        io.check(stride, buf.stride, f)
        io.check(vertex_num, buf.size, f)
        io.check(stride, 8 + uv_num * 4 * (1 + use_float32), f)
        return StaticMeshVertexBuffer(uv_num, use_float32, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint32(f, self.uv_num)
        io.write_uint32(f, self.stride)
        io.write_uint32(f, self.vertex_num)
        io.write_uint32(f, self.use_float32)
        io.write_null(f)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        def unpack(i):
            mask8bit = 0xff
            x = i & mask8bit
            y = (i >> 8) & mask8bit
            z = (i >> 16) & mask8bit
            return [x, y, z]
        uv_type = 'f' * self.use_float32 + 'e' * (not self.use_float32)
        parsed = struct.unpack('<' + ('I' * 2 + uv_type * 2 * self.uv_num) * self.size, self.buf)
        stride = 2 + 2 * self.uv_num
        normals = [parsed[i * stride + 1] for i in range(self.size)]
        normal = [unpack(n) for n in normals]
        texcoords = []
        for j in range(self.uv_num):
            texcoord = [parsed[i * stride + 2 + j * 2: i * stride + 2 + j * 2 + 2] for i in range(self.size)]
            texcoords.append(texcoord)
        return normal, texcoords

    def import_from_blender(self, normal, texcoords, uv_num):
        """Update buffer."""
        uv_type = 'f' * self.use_float32 + 'e' * (not self.use_float32)
        self.uv_num = uv_num
        self.stride = 8 + (1 + self.use_float32) * 4 * self.uv_num
        self.size = len(normal)
        self.vertex_num = self.size
        buf = normal
        for texcoord in texcoords:
            buf = [b + t for b, t in zip(buf, texcoord)]
        buf = flatten(buf)
        self.buf = struct.pack('<' + ('B' * 8 + uv_type * 2 * self.uv_num) * self.size, *buf)


class ColorVertexBuffer(VertexBuffer):
    """Vertex colors."""
    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        stride = io.read_uint32(f)
        vertex_num = io.read_uint32(f)
        if stride > 0:
            buf = Buffer.read(f, name=name)
            io.check(stride, buf.stride)
            io.check(vertex_num, buf.size, f)
            return ColorVertexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)
        else:
            return ColorVertexBuffer(stride, vertex_num, None, f.tell(), name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint32(f, self.stride)
        io.write_uint32(f, self.vertex_num)
        if self.buf is not None:
            super().write(f)

    def update(self, vertex_count):
        """Update buffer."""
        self.vertex_num = vertex_count
        self.size = vertex_count
        self.buf = b'ff' * self.size * self.stride

    def disable(self):
        """Disable vertex colors."""
        self.buf = None
        self.stride = 0
        self.vertex_num = 0


class SkeletalMeshVertexBuffer(VertexBuffer):
    """Normals, positions, and UV maps for UE4 skeletal mesh."""
    def __init__(self, uv_num, use_float32, scale, stride, size, buf, offset, name):
        """Constructor."""
        self.uv_num = uv_num
        self.use_float32 = use_float32
        self.scale = scale
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        uv_num = io.read_uint32(f)
        use_float32UV = io.read_uint32(f)
        scale = io.read_vec3_f32(f)
        io.check(scale, [1, 1, 1], 'SkeletalMeshVertexBuffer: MeshExtension is not (1.0, 1.0 ,1.0))')
        io.read_null_array(f, 3, 'SkeletalMeshVertexBuffer: MeshOrigin is not (0,0,0))')
        buf = Buffer.read(f, name=name)
        return SkeletalMeshVertexBuffer(uv_num, use_float32UV, scale, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint32(f, self.uv_num)
        io.write_uint32(f, self.use_float32)
        io.write_vec3_f32(f, self.scale)
        io.write_null_array(f, 3)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        def unpack(i):
            mask8bit = 0xff
            x = i & mask8bit
            y = (i >> 8) & mask8bit
            z = (i >> 16) & mask8bit
            return [x, y, z]
        uv_type = 'f' * self.use_float32 + 'e' * (not self.use_float32)
        parsed = struct.unpack('<' + ('I' * 2 + 'fff' + uv_type * 2 * self.uv_num) * self.size, self.buf)
        stride = 5 + 2 * self.uv_num
        normals = [parsed[i * stride + 1] for i in range(self.size)]
        normal = [unpack(n) for n in normals]
        # tangent = [n[0:4] for n in normals]
        position = [parsed[i * stride + 2: i * stride + 5] for i in range(self.size)]
        texcoords = []
        for j in range(self.uv_num):
            texcoord = [parsed[i * stride + 5 + j * 2: i * stride + 5 + j * 2 + 2] for i in range(self.size)]
            texcoords.append(texcoord)
        return normal, position, texcoords

    def get_range(self):
        """Get range of vertex positions."""
        uv_type = 'f' * self.use_float32 + 'e' * (not self.use_float32)
        parsed = struct.unpack('<' + ('B' * 8 + 'fff' + uv_type * 2 * self.uv_num) * self.size, self.buf)
        stride = 11 + 2 * self.uv_num
        position = [parsed[i * stride + 8: i * stride + 11] for i in range(self.size)]
        x = [pos[0] for pos in position]
        y = [pos[1] for pos in position]
        z = [pos[2] for pos in position]
        return [max(x) - min(x), max(y) - min(y), max(z) - min(z)]

    def import_from_blender(self, normal, position, texcoords, uv_num):
        """Update buffer."""
        uv_type = 'f' * self.use_float32 + 'e' * (not self.use_float32)
        self.uv_num = uv_num
        self.stride = 20 + (1 + self.use_float32) * 4 * self.uv_num
        self.size = len(normal)
        self.vertex_num = self.size
        buf = [n + p for n, p in zip(normal, position)]
        for texcoord in texcoords:
            buf = [b + t for b, t in zip(buf, texcoord)]
        buf = flatten(buf)
        self.buf = struct.pack('<' + ('B' * 8 + 'fff' + uv_type * 2 * self.uv_num) * self.size, *buf)


def flatten(array):
    """Flatten list."""
    return [x for row in array for x in row]


class SkinWeightVertexBuffer4(VertexBuffer):
    """Skin weights for UE4 skeletal mesh."""
    def __init__(self, extra_bone_flag, stride, size, buf, offset, name):
        """Constructor."""
        self.extra_bone_flag = extra_bone_flag
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        extra_bone_flag = io.read_uint32(f)  # if stride is 16 or not
        vertex_num = io.read_uint32(f)
        buf = Buffer.read(f, name=name)
        io.check(vertex_num, buf.size, f)
        io.check(extra_bone_flag, buf.stride == 16, f)
        return SkinWeightVertexBuffer4(extra_bone_flag, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_uint32(f, self.extra_bone_flag)
        io.write_uint32(f, self.vertex_num)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        parsed = struct.unpack('<' + 'B' * len(self.buf), self.buf)
        joint = [parsed[i * self.stride: i * self.stride + self.stride // 2] for i in range(self.size)]
        weight = [parsed[i * self.stride + self.stride // 2: (i + 1) * self.stride] for i in range(self.size)]
        return joint, weight

    def import_from_blender(self, joint, weight, extra_bone_flag):
        """Update buffer."""
        self.size = len(joint)
        self.vertex_num = self.size
        self.extra_bone_flag = extra_bone_flag
        self.stride = 8 * (1 + self.extra_bone_flag)
        buf = [j + w for j, w in zip(joint, weight)]
        buf = flatten(buf)
        self.buf = struct.pack('<' + 'B' * self.size * self.stride, *buf)


class SkinWeightVertexBuffer5(VertexBuffer):
    """Skin weights for UE5 skeletal mesh."""
    def __init__(self, influence_count, stride, size, buf, offset, name):
        """Constructor."""
        self.influence_count = influence_count
        super().__init__(stride, size, buf, offset, name)

    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        io.read_null(f)
        influence_count = io.read_uint32(f)
        influence_x_vertex = io.read_uint32(f)
        vertex_count = io.read_uint32(f)
        io.check(influence_count * vertex_count, influence_x_vertex)
        io.read_null(f)
        buf = Buffer.read(f, name=name)
        return SkinWeightVertexBuffer5(influence_count, buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        io.write_null(f)
        io.write_uint32(f, self.influence_count)
        io.write_uint32(f, self.size // 2)
        io.write_uint32(f, self.size // 2 // self.influence_count)
        io.write_null(f)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        parsed = struct.unpack('<' + 'B' * len(self.buf), self.buf)
        stride = self.influence_count * 2
        size = self.size // self.influence_count // 2
        joint = [parsed[i * stride: i * stride + self.influence_count] for i in range(size)]
        weight = [parsed[i * stride + stride // 2: (i + 1) * stride] for i in range(size)]
        return joint, weight

    def import_from_blender(self, joint, weight):
        """Update buffer."""
        self.influence_count = len(joint[0])
        buf = [j + w for j, w in zip(joint, weight)]
        buf = flatten(buf)
        self.size = len(buf)
        self.buf = struct.pack('<' + 'B' * self.size * self.stride, *buf)


class StaticIndexBuffer(Buffer):
    """Index buffer for static mesh."""
    def __init__(self, uint32_flag, stride, size, ib, offset, name, version):
        """Constructor."""
        self.uint32_flag = uint32_flag
        self.version = version
        super().__init__(stride, size, ib, offset, name)

    @staticmethod
    def read(f, version, name=''):
        """Read function."""
        uint32_flag = io.read_uint32(f)  # 0: uint16 id, 1: uint32 id
        buf = Buffer.read(f, name=name)
        if version >= '4.27':
            io.read_null(f)
        # buf.stride==1
        # buf.size==index_count*(2+2*uint32_flag)
        return StaticIndexBuffer(uint32_flag, buf.stride, buf.size, buf.buf, buf.offset, name, version)

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.uint32_flag)
        super().write(f)
        if self.version >= '4.27':
            io.write_null(f)

    def get_meta(self):
        """Get meta data."""
        stride = 2 + 2 * self.uint32_flag
        size = len(self.buf) // stride
        return self.offset, stride, size

    def parse(self):
        """Parse buffer."""
        _, stride, size = self.get_meta()
        form = [None, None, 'H', None, 'I']
        indices = struct.unpack('<' + form[stride] * size, self.buf)
        return indices

    def update(self, new_ids, use_uint32=False):
        """Update buffer."""
        form = [None, None, 'H', None, 'I']
        self.uint32_flag = use_uint32
        stride = 2 + 2 * use_uint32
        size = len(new_ids)
        self.size = size * stride
        self.stride = 1
        self.buf = struct.pack('<' + form[stride] * size, *new_ids)

    def disable(self):
        """Disable buffer."""
        self.update([])


class SkeletalIndexBuffer(Buffer):
    """Index buffer for skeletal mesh."""

    @staticmethod
    def read(f, name=''):
        """Read function."""
        stride = io.read_uint8(f)  # 2: uint16 id, 4: uint32 id
        buf = Buffer.read(f, name=name)
        io.check(stride, buf.stride)
        return SkeletalIndexBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint8(f, self.stride)
        super().write(f)

    def parse(self):
        """Parse buffer."""
        form = [None, None, 'H', None, 'I']
        indices = struct.unpack('<' + form[self.stride] * self.size, self.buf)
        return indices

    def update(self, new_ids, stride):
        """Update buffer."""
        form = [None, None, 'H', None, 'I']
        self.size = len(new_ids)
        # new_ids = [new_ids[i*3:(i+1)*3] for i in range(self.size//3)]
        # new_ids = [[ids[0], ids[2], ids[1]] for ids in new_ids]
        # new_ids = flatten(new_ids)
        # print(len(new_ids))
        self.stride = stride
        self.buf = struct.pack('<' + form[self.stride] * self.size, *new_ids)


class KDIBuffer(Buffer):
    """KDI buffers."""
    @staticmethod
    def read(f, name=''):
        """Read function."""
        one = io.read_uint16(f)
        io.check(one, 1, f)
        buf = Buffer.read(f, name=name)
        return KDIBuffer(buf.stride, buf.size, buf.buf, buf.offset, name)

    def write(self, f):
        """Write function."""
        io.write_uint16(f, 1)
        super().write(f)
