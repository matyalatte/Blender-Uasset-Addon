"""Class for animations.

Notes:
    It can't parse animation data yet.
    It'll just get frame count, bone ids, and compressed binary.
"""
import os
from ..util import io_util as io
from .acl import CompressedClip


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


def seek_none(f, none_id):
    """Read binary data until find 'None' property."""
    buf = f.read(8)
    none_bin = none_id.to_bytes(8, byteorder="little")
    size = io.get_size(f)
    while buf != none_bin:
        buf = b''.join([buf[1:], f.read(1)])
        if f.tell() == size:
            raise RuntimeError('None property not found. This is an unexpected error.')


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
        if unk[0] != 0x80:
            unk2 = f.read(27*io.read_uint32(f))
        else:
            b = f.read(1)
            if b == b'\x7f':
                unk = b''.join([unk, b'\x7f'])
            else:
                f.seek(-1, 1)
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


class AnimSequence:
    """Animation data."""
    def __init__(self, uasset, unk, guid, format_bytes, unk_ids, bone_ids,
                 unk2, raw_size, compressed_size, compressed_data, verbose):
        """Constructor."""
        self.uasset = uasset
        self.unk = unk
        self.guid = guid
        self.format_bytes = format_bytes
        self.unk_ids = unk_ids
        self.bone_ids = bone_ids
        self.unk2 = unk2
        self.raw_size = raw_size
        self.compressed_size = compressed_size
        self.compressed_data = compressed_data
        if verbose:
            self.print()
            # Todo: Remove this for released version
            # with open(f'{uasset.file}.bin', 'wb') as f:
            #    self.compressed_data.write(f)

    @staticmethod
    def read(f, uasset, verbose=False):
        """Read function."""

        def get_skeleton_import(imports):
            for imp, i in zip(imports, range(len(imports))):
                if imp.class_name == 'Skeleton':
                    return imp, i
        # Skip Notifies
        skeleton_imp, import_id = get_skeleton_import(uasset.imports)

        unk = seek_skeleton(f, import_id)
        none_id = uasset.name_list.index('None')
        if uasset.version != 'ff7r':
            io.check(io.read_uint64(f), none_id)
        io.read_null(f)
        guid = f.read(16)
        io.check(io.read_uint16(f), 1)  # StripFlags
        io.check(io.read_uint32(f), 1)  # bSerializeCompressedData?

        # UAnimSequence::SerializeCompressedData
        format_bytes = io.read_uint8_array(f, length=4)  # key format and trs formats
        if format_bytes[0] < 3:
            raise RuntimeError('Non-ACL animations are unsupported.')
        unk_ids = io.read_uint32_array(f)  # CompressedTrackOffsets?
        io.check(io.read_uint32(f), 0)  # CompressedScaleOffsets OffsetData?
        io.check(io.read_uint32(f), 2)  # CompressedScaleOffsets StripSize?
        bone_ids = io.read_uint32_array(f)

        offset = f.tell()
        if uasset.version == 'ff7r':
            if f.read(2) == b'\x00\x03':
                _ = [UnkData.read(f) for i in range(io.read_uint32(f))]  # CompressedCurveData?
            else:
                io.check(f.read(1), b'\x01', f)
        else:
            seek_none(f, none_id)
        size = f.tell() - offset
        f.seek(offset)
        unk2 = f.read(size)

        raw_size = io.read_uint32(f)  # CompressedRawDataSize
        compressed_size = io.read_uint32(f)
        if uasset.version != 'ff7r':
            io.read_const_uint32(f, 0)
        compressed_data = CompressedClip.read(f)
        return AnimSequence(uasset, unk, guid, format_bytes, unk_ids, bone_ids,
                            unk2, raw_size, compressed_size, compressed_data, verbose)

    def write(self, f):
        """Write function."""
        f.write(self.unk)
        if self.uasset.version != 'ff7r':
            io.write_uint64(f, self.uasset.name_list.index('None'))
        io.write_null(f)
        f.write(self.guid)

        io.write_uint16(f, 1)
        io.write_uint32(f, 1)
        io.write_uint8_array(f, self.format_bytes)
        io.write_uint32_array(f, self.unk_ids, with_length=True)
        io.write_uint32(f, 0)
        io.write_uint32(f, 2)

        io.write_uint32_array(f, self.bone_ids, with_length=True)
        f.write(self.unk2)

        io.write_uint32(f, self.raw_size)
        offset = f.tell()
        io.write_uint32(f, self.compressed_data.size)
        if self.uasset.version != 'ff7r':
            io.write_uint32(f, 0)
        self.compressed_data.write(f)
        end_offset = f.tell()
        f.seek(offset)
        io.write_uint32(f, self.compressed_data.size)
        f.seek(end_offset)

    def print(self):
        """Print meta data."""
        self.compressed_data.print(['bone id: ' + str(i) for i in self.bone_ids])

    def get_skeleton_path(self):
        """Get path to skeleton asset."""
        skeleton_path = [imp.parent_name for imp in self.uasset.imports if imp.class_name == 'Skeleton'][0]

        def get_actual_path(target_asset_path, source_asset_path, source_actual_path):
            source_asset_dir = os.path.dirname(source_asset_path)
            rel_path = os.path.relpath(os.path.dirname(target_asset_path), start=source_asset_dir)
            base = os.path.basename(target_asset_path) + '.uasset'
            return os.path.normpath(os.path.join(os.path.dirname(source_actual_path), rel_path, base))

        return get_actual_path(skeleton_path, self.uasset.asset_path, self.uasset.actual_path)

    def get_animation_path(self):
        """Get path to animation asset."""
        return self.uasset.actual_path

    def get_animation_name(self):
        """Get animation name."""
        return self.uasset.asset_name

    def import_anim_data(self, anim_data):
        """Import animation data."""
        self.compressed_data.import_anim_data(anim_data)
