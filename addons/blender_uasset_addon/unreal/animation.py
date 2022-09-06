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
    ANIMATION_KEY_FORMAT = [
        "AKF_ConstantKeyLerp",
        "AKF_VariableKeyLerp",
        "AKF_PerTrackCompression",
        "AKF_ACLDefault",
        "AKF_ACLCustom",
        "AKF_ACLSafe",
    ]

    ANIMATION_COMPRESSION_FORMAT = [
        "ACF_None",
        "ACF_Float96NoW",
        "ACF_Fixed48NoW",
        "ACF_IntervalFixed32NoW",
        "ACF_Fixed32NoW",
        "ACF_Float32NoW",
        "ACF_Identity"
    ]

    def __init__(self, offset, uasset, num_frames, unk, unk2, guid, format_bytes,
                 track_offsets, scale_offsets, scale_offsets_stripsize, bone_ids,
                 unk3, raw_size, compressed_size, compressed_data, verbose):
        """Constructor."""
        self.offset = offset
        self.uasset = uasset
        self.num_frames = num_frames
        self.unk = unk
        self.unk2 = unk2
        self.guid = guid
        self.format_bytes = format_bytes
        self.is_acl = format_bytes[0] >= 3
        self.track_offsets = track_offsets
        self.scale_offsets = scale_offsets
        self.scale_offsets_stripsize = scale_offsets_stripsize
        self.bone_ids = bone_ids
        self.unk3 = unk3
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
        offset = f.tell()
        if uasset.unversioned:
            unv_head = io.read_uint8_array(f, 2)
            is_last = unv_head[1] % 2 == 0
            while is_last:
                unv_head = io.read_uint8_array(f, 2)
                is_last = unv_head[1] % 2 == 0
                if f.tell() > 100:
                    raise RuntimeError('Parse Failed.')
        else:
            f.seek(25)
        unk_size = f.tell() - offset
        f.seek(offset)
        unk = f.read(unk_size)
        num_frames = io.read_uint32(f)

        def get_skeleton_import(imports):
            for imp, i in zip(imports, range(len(imports))):
                if imp.class_name == 'Skeleton':
                    return imp, i
        # Skip Notifies
        skeleton_imp, import_id = get_skeleton_import(uasset.imports)
        unk2 = seek_skeleton(f, import_id)
        none_id = uasset.name_list.index('None')
        if uasset.version != 'ff7r':
            io.check(io.read_uint64(f), none_id)
        io.read_null(f)
        guid = f.read(16)
        io.check(io.read_uint16(f), 1)  # StripFlags
        io.check(io.read_uint32(f), 1)  # bSerializeCompressedData?

        # UAnimSequence::SerializeCompressedData
        format_bytes = io.read_uint8_array(f, length=4)  # key format and trs formats
        key_format = AnimSequence.ANIMATION_KEY_FORMAT[format_bytes[0]]
        if key_format not in ['AKF_PerTrackCompression', 'AKF_ACLDefault']:
            raise RuntimeError(f'Unsupported key format. ({key_format})')

        track_offsets = io.read_int32_array(f)  # CompressedTrackOffsets
        scale_offsets = io.read_uint32_array(f)  # CompressedScaleOffsets
        scale_offsets_stripsize = io.read_uint32(f)
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
        unk3 = f.read(size)

        raw_size = io.read_uint32(f)  # CompressedRawDataSize
        compressed_size = io.read_uint32(f)
        if uasset.version not in ['ff7r', 'kh3']:
            io.read_const_uint32(f, 0)
        if format_bytes[0] >= 3:
            compressed_data = CompressedClip.read(f)
        else:
            compressed_data = CompressedData.read(f, compressed_size, num_frames, len(bone_ids),
                                                  track_offsets, scale_offsets)
        return AnimSequence(offset, uasset, num_frames, unk, unk2, guid, format_bytes,
                            track_offsets, scale_offsets, scale_offsets_stripsize, bone_ids,
                            unk3, raw_size, compressed_size, compressed_data, verbose)

    def write(self, f):
        """Write function."""
        f.write(self.unk)
        io.write_uint32(f, self.num_frames)
        f.write(self.unk2)
        if self.uasset.version != 'ff7r':
            io.write_uint64(f, self.uasset.name_list.index('None'))
        io.write_null(f)
        f.write(self.guid)

        io.write_uint16(f, 1)
        io.write_uint32(f, 1)
        io.write_uint8_array(f, self.format_bytes)
        io.write_int32_array(f, self.track_offsets, with_length=True)
        io.write_uint32_array(f, self.scale_offsets, with_length=True)
        io.write_uint32(f, self.scale_offsets_stripsize)

        io.write_uint32_array(f, self.bone_ids, with_length=True)
        f.write(self.unk3)

        io.write_uint32(f, self.raw_size)
        offset = f.tell()
        io.write_uint32(f, self.compressed_data.size)
        if self.uasset.version not in ['ff7r', 'kh3']:
            io.write_uint32(f, 0)
        self.compressed_data.write(f)
        end_offset = f.tell()
        f.seek(offset)
        io.write_uint32(f, self.compressed_data.size)
        f.seek(end_offset)

    def print(self):
        """Print meta data."""
        print(f"AnimSequence (offset: {self.offset})")
        print(f"  KeyEncodingFormat: {self.get_key_format()}")
        print(f"  TranslationCompressionFormat: {self.get_translation_format()}")
        print(f"  RotationCompressionFormat: {self.get_rotation_format()}")
        print(f"  ScaleCompressionFormat: {self.get_scale_format()}")
        # print(f"  TrackOffsets: {self.track_offsets}")
        # print(f"  ScaleOffsets: {self.scale_offsets}")
        if self.compressed_data is not None:
            self.compressed_data.print()

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

    def get_key_format(self):
        """Get AnimationKeyFormat as a string."""
        return AnimSequence.ANIMATION_KEY_FORMAT[self.format_bytes[0]]

    def get_translation_format(self):
        """Get TranslationCompressionFormat as a string."""
        return AnimSequence.ANIMATION_COMPRESSION_FORMAT[self.format_bytes[1]]

    def get_rotation_format(self):
        """Get TranslationCompressionFormat as a string."""
        return AnimSequence.ANIMATION_COMPRESSION_FORMAT[self.format_bytes[2]]

    def get_scale_format(self):
        """Get TranslationCompressionFormat as a string."""
        return AnimSequence.ANIMATION_COMPRESSION_FORMAT[self.format_bytes[3]]


class CompressedData:
    """Compressed data for the standard (non-ACL) animation tracks."""
    def __init__(self, offset, bone_tracks, size):
        """Constructor."""
        self.offset = offset
        self.bone_tracks = bone_tracks
        self.size = size

    @staticmethod
    def read(f, size, num_frames, num_bones, track_offsets, scale_offsets, verbose=False):
        """Read function."""
        offset = f.tell()
        track_offsets = [track_offsets[i * 2: (i + 1) * 2] for i in range(len(track_offsets) // 2)]
        track_offsets = [to + [so] for to, so in zip(track_offsets, scale_offsets)]

        bone_tracks = [BoneTrack.read(f, to, num_frames, offset) for to in track_offsets]
        io.check(f.tell() - offset, size)
        return CompressedData(offset, bone_tracks, size)

    def write(self, f):
        """Write function."""
        # f.write(self.bin)

    def print(self):
        """Print metadata."""
        print(f"CompressedData (offset: {self.offset})")


class RangeData:
    """Range data for range reduction."""

    def __init__(self, min_xyz, extent_xyz):
        """Constructor."""
        self.min_xyz = min_xyz
        self.extent_xyz = extent_xyz

    @staticmethod
    def read(f, component_mask):
        """Read function."""
        min_xyz = [0, 0, 0]
        extent_xyz = [0, 0, 0]
        if component_mask & 1:
            min_xyz[0] = io.read_float32(f)
            extent_xyz[0] = io.read_float32(f)
        if component_mask & 2:
            min_xyz[1] = io.read_float32(f)
            extent_xyz[1] = io.read_float32(f)
        if component_mask & 4:
            min_xyz[2] = io.read_float32(f)
            extent_xyz[2] = io.read_float32(f)
        range_data = RangeData(min_xyz, extent_xyz)
        return range_data

    @staticmethod
    def unpack_elem(elem, range_min, range_extent):
        """Unpack a normalized value."""
        return elem * range_extent + range_min

    def unpack(self, xyz):
        """Unpack a normalized vector."""
        vec = [RangeData.unpack_elem(i, m, e) for i, m, e in zip(xyz, self.min_xyz, self.extent_xyz)]
        return vec


class BoneTrack:
    """Animation track for a bone."""

    def __init__(self):
        """Constructor."""
        self.use_default = [False] * 3
        self.keys = [[], [], []]
        self.times = [[], [], []]

    @staticmethod
    def read(f, track_offsets, num_frames, first_track_offset):
        """Read function."""
        trans_ofs = f.tell()
        bone_track = BoneTrack()
        sizes = [0, 0, 0]
        for i, ofs in zip(range(3), track_offsets):
            if ofs == -1:
                bone_track.use_default[i] = True
                continue
            start_ofs = f.tell()
            keys, times = BoneTrack.read_per_track(f, num_frames, first_track_offset, quat=i == 1)
            sizes[i] = f.tell() - start_ofs
            bone_track.keys[i] = keys
            bone_track.times[i] = times
        bone_track.keys[0], bone_track.keys[1] = bone_track.keys[1], bone_track.keys[0]
        bone_track.times[0], bone_track.times[1] = bone_track.times[1], bone_track.times[0]
        track_offsets = [track_offsets[2]] + track_offsets[:2]
        sizes = [sizes[2]] + sizes[:2]
        for size, ofs in zip(sizes, track_offsets):
            if ofs == -1:
                continue
            io.check(ofs, trans_ofs - first_track_offset)
            trans_ofs += size
        return bone_track

    @staticmethod
    def read_per_track(f, num_frames, offset, quat=False):
        """Read a track."""
        info = io.read_uint32(f)  # PackedInfo
        key_format = AnimSequence.ANIMATION_COMPRESSION_FORMAT[info >> 28]
        component_mask = (info >> 24) & 0xF
        num_keys = info & 0xFFFFFF
        has_time_tracks = (component_mask & 8) != 0
        if key_format in ['ACF_None']:
            raise RuntimeError(f'Unsupported format. ({key_format})')

        if key_format == ' ACF_Float96NoW' and component_mask == 0 and not quat:
            component_mask = 7

        if key_format == 'ACF_IntervalFixed32NoW':
            range_data = RangeData.read(f, component_mask)
            if quat:
                def unpack(i):
                    mask10bit = 0b1111111111
                    mask11bit = 0b11111111111
                    z = i & mask10bit
                    y = (i >> 10) & mask11bit
                    x = (i >> 21) & mask11bit
                    return [x / 1023 - 1, y / 1023 - 1, z / 511 - 1]
            else:
                def unpack(i):
                    mask10bit = 0b1111111111
                    mask11bit = 0b11111111111
                    x = i & mask10bit
                    y = (i >> 10) & mask11bit
                    z = (i >> 21) & mask11bit
                    return [x / 511 - 1, y / 1023 - 1, z / 1023 - 1]

        keys = []
        for i in range(num_keys):
            vec = [0, 0, 0]
            if key_format == 'ACF_Float96NoW':
                if component_mask & 7:
                    if component_mask & 1:
                        vec[0] = io.read_float32(f)
                    if component_mask & 2:
                        vec[1] = io.read_float32(f)
                    if component_mask & 4:
                        vec[2] = io.read_float32(f)
            elif key_format == 'ACF_Fixed48NoW':
                if quat:
                    def decode(i):
                        return (i - 32767) / 32767
                else:
                    def decode(i):
                        return i - 255

                if component_mask & 7:
                    if component_mask & 1:
                        vec[0] = decode(io.read_uint16(f))
                    if component_mask & 2:
                        vec[1] = decode(io.read_uint16(f))
                    if component_mask & 4:
                        vec[2] = decode(io.read_uint16(f))
            elif key_format == 'ACF_IntervalFixed32NoW':
                vec32bit = io.read_uint32(f)
                vec = unpack(vec32bit)
                vec = range_data.unpack(vec)
            elif key_format != 'ACF_Identity':
                raise RuntimeError(f'Unsupported format. ({key_format})')
            keys.append(vec)

        num_padding = (4 - f.tell() + offset) % 4
        io.check(f.read(num_padding), b'\x55' * num_padding)

        times = []
        if has_time_tracks:
            if num_frames < 256:
                times = io.read_uint8_array(f, length=num_keys)
            else:
                times = io.read_uint16_array(f, length=num_keys)
            num_padding = (4 - f.tell() + offset) % 4
            io.check(f.read(num_padding), b'\x55' * num_padding)
            io.check(len(keys), len(times))
        else:
            interval = num_frames / (len(keys) - 1)
            times = [interval * i for i in range(len(keys))]
        return keys, times
