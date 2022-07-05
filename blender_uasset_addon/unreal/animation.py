"""Class for animations.

Notes:
    It can't parse animation data yet.
    It'll just get frame count, bone ids, and compressed binary.
"""
# Todo: Uncompress animation data.
from ..util import io_util as io


def read_unversioned_header(f):
    """Skip unversioned headers."""
    offset = f.tell()
    unv_head = io.read_uint8_array(f, 2)
    is_last = unv_head[1] % 2 == 0
    while is_last:
        unv_head = io.read_uint8_array(f, 2)
        is_last = unv_head[1] % 2 == 0
        if f.tell() - offset > 100:
            raise RuntimeError('Parse Failed. ')
    size = f.tell() - offset
    f.seek(offset)
    headers = f.read(size)
    return headers


def seek_skeleton(f, import_id):
    """Read binary data until find skeleton import ids."""
    offset = f.tell()
    buf = f.read(3)
    size = io.get_size(f)
    while True:
        while buf != b'\xff' * 3:
            if b'\xff' not in buf:
                buf = f.read(3)
            else:
                buf = b''.join([buf[1:], f.read(1)])
            if f.tell() == size:
                raise RuntimeError('Skeleton id not found. This is an unexpected error.')
        f.seek(-4, 1)
        imp_id = -io.read_int32(f) - 1
        if imp_id == import_id:
            break
        buf = f.read(3)
    size = f.tell() - offset
    f.seek(offset)
    return f.read(size)


class UnkData:
    """Animation data."""
    def __init__(self, unk, unk2, unk_int, unk_int2):
        """Constructor."""
        self.unk = unk
        self.unk2 = unk2
        self.unk_int = unk_int
        self.unk_int2 = unk_int2

    @staticmethod
    def read(f):
        """Read function."""
        io.check(f.read(4), b'\x00\x02\x01\x05')
        unk = f.read(8)
        if unk[0] != b'\x80':
            unk2 = f.read(27*io.read_uint32(f))
        else:
            unk2 = None
        unk_int = io.read_uint32(f)
        unk_int2 = io.read_uint32(f)
        io.read_const_uint32(f, 4)
        return UnkData(unk, unk2, unk_int, unk_int2)

    def write(self, f):
        """Write function."""
        f.write(b'\x00\x02\x01\x05')
        f.write(self.unk)
        if self.unk2 is not None:
            io.write_uint32(f, len(self.unk2) // 27)
            f.write(self.unk2)
        io.write_uint32(f, self.unk_int)
        io.write_uint32(f, self.unk_int2)
        io.write_uint32(f, 4)


class RawAnimData:
    """Raw animation binary data."""
    def __init__(self, size, unk, bone_count, unk_int, unk2, frame_count, fps, rest):
        """Constructor."""
        self.size = size
        self.unk = unk
        self.bone_count = bone_count
        self.unk_int = unk_int
        self.unk2 = unk2
        self.frame_count = frame_count
        self.fps = fps
        self.rest = rest

    @staticmethod
    def read(f, size):
        """Read function."""
        offset = f.tell()
        unk = f.read(8)
        io.read_const_uint32(f, 3)
        bone_count = io.read_uint16(f)
        unk_int = io.read_uint16(f)
        unk2 = f.read(8)
        frame_count = io.read_uint32(f)
        fps = io.read_uint32(f)
        rest = f.read(size - (f.tell() - offset))
        return RawAnimData(size, unk, bone_count, unk_int, unk2, frame_count, fps, rest)

    def write(self, f):
        """Write function."""
        f.write(self.unk)
        io.write_uint32(f, 3)
        io.write_uint16(f, self.bone_count)
        io.write_uint16(f, self.unk_int)
        f.write(self.unk2)
        io.write_uint32(f, self.frame_count)
        io.write_uint32(f, self.fps)
        f.write(self.rest)


class AnimSequence:
    """Animation data."""
    def __init__(self, uasset, unv_header, frame_count, bone_ids, notifies, guid, unk_ary, unk_int, raw_data, verbose):
        """Constructor."""
        self.uasset = uasset
        self.unv_header = unv_header
        self.frame_count = frame_count
        self.bone_ids = bone_ids
        self.notifies = notifies
        self.guid = guid
        self.unk_ary = unk_ary
        self.unk_int = unk_int
        self.raw_data = raw_data
        if verbose:
            self.print()
            # Todo: Remove this for released version
            # with open(f'{uasset.file}.bin', 'wb') as f:
            #    self.raw_data.write(f)

    @staticmethod
    def read(f, uasset, verbose):
        """Read function."""
        unv_header = read_unversioned_header(f)
        frame_count = io.read_uint32(f)

        def read_bone_id(f):
            io.check(f.read(2), b'\x00\x03', f)
            return io.read_uint32(f)

        bone_count = io.read_uint32(f)
        io.check(f.read(3), b'\x80\x03\x01')
        bone_ids = [0] + [read_bone_id(f) for i in range(bone_count - 1)]

        def get_skeleton_import(imports):
            for imp, i in zip(imports, range(len(imports))):
                if imp.class_name == 'Skeleton':
                    return imp, i
        # Skip Notifies
        skeleton_imp, import_id = get_skeleton_import(uasset.imports)

        notifies = seek_skeleton(f, import_id)
        io.read_null(f)
        guid = f.read(16)
        io.check(io.read_uint16(f), 1)
        io.check(io.read_uint32_array(f, length=5), [1, 3, 0, 0, 2])
        io.check(io.read_uint32_array(f), bone_ids)

        io.check(f.read(2), b'\x00\x03', f)

        unk_ary = [UnkData.read(f) for i in range(io.read_uint32(f))]

        unk_int = io.read_uint32(f)  # some offset?
        raw_size = io.read_uint32(f)
        io.read_const_uint32(f, raw_size)
        raw_data = RawAnimData.read(f, raw_size)
        return AnimSequence(uasset, unv_header, frame_count, bone_ids, notifies,
                            guid, unk_ary, unk_int, raw_data, verbose)

    def write(self, f):
        """Write function."""
        f.write(self.unv_header)
        io.write_uint32(f, self.frame_count)

        def write_bone_id(f, index):
            f.write(b'\x00\x03')
            io.write_uint32(f, index)

        io.write_uint32(f, len(self.bone_ids))
        f.write(b'\x80\x03\x01')
        list(map(lambda i: write_bone_id(f, i), self.bone_ids[1:]))

        f.write(self.notifies)
        io.write_null(f)
        f.write(self.guid)

        io.write_uint16(f, 1)
        io.write_uint32_array(f, [1, 3, 0, 0, 2])
        io.write_uint32_array(f, self.bone_ids, with_length=True)
        f.write(b'\x00\x03')
        io.write_uint32(f, len(self.unk_ary))
        list(map(lambda x: x.write(f), self.unk_ary))

        io.write_uint32(f, self.unk_int)
        io.write_uint32(f, self.raw_data.size)
        io.write_uint32(f, self.raw_data.size)
        self.raw_data.write(f)

    def print(self):
        """Print meta data."""
        print(f'frame count: {self.frame_count}')
        print(f'use bone count: {len(self.bone_ids)}')
        print(f'compressed data size: {self.raw_data.size}')
