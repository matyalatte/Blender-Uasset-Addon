"""Classes for ACL data.

Notes:
    Only supports ACL v1.1.0.
    https://github.com/nfrechette/acl/blob/v1.1.0/includes/acl/core/compressed_clip.h
"""
import ctypes as c
import math
import struct
from ..util import io_util as io


class ClipHeader(c.LittleEndianStructure):
    """Compressed clip header."""

    _pack_ = 1
    _fields_ = [
        ("num_bones", c.c_uint16),
        ("num_segments", c.c_uint16),
        ("rotation_format", c.c_uint8),
        ("translation_format", c.c_uint8),
        ("scale_format", c.c_uint8),
        ("clip_range_reduction", c.c_uint8),
        ("segment_range_reduction", c.c_uint8),
        ("has_scale", c.c_uint8),
        ("default_scale", c.c_uint8),
        ("padding", c.c_uint8),
        ("num_samples", c.c_uint32),
        ("sample_rate", c.c_uint32),
        ("segment_headers_offset", c.c_uint16),
        ("default_tracks_bitset_offset", c.c_uint16),
        ("constant_tracks_bitset_offset", c.c_uint16),
        ("constant_tracks_data_offset", c.c_uint16),
        ("clip_range_data_offset", c.c_uint16),
        ("padding2", c.c_uint16)
    ]

    ROTATION_FORMAT = [
        "Quat_128",		        # [x,y,z,w] with float32
        "QuatDropW_96",			# [x,y,z] with float32 (w is dropped)
        "QuatDropW_48",			# [x,y,z] with [16,16,16] bits (w is dropped)
        "QuatDropW_32",			# [x,y,z] with [11,11,10] bits (w is dropped)
        "QuatDropW_Variable"    # [x,y,z] with [N,N,N] bits (same number of bits per component)
    ]

    VECTOR_FORMAT = [
        "Vector3_96",		 # [x,y,z] with float32
        "Vector3_48",		 # [x,y,z] with [16,16,16] bits
        "Vector3_32",		 # [x,y,z] with [11,11,10] bits
        "Vector3_Variable"	 # [x,y,z] with [N,N,N] bits (same number of bits per component)
    ]

    RANGE_REDUCTION_FLAGS = [
        'None',
        'Rotations',
        'Translations',
        None,
        'Scales',
        None,
        None,
        'AllTracks'
    ]

    @staticmethod
    def read(f):
        """Read function."""
        header = ClipHeader()
        header.offset = f.tell()
        f.readinto(header)
        return header

    def write(self, f):
        """Write function."""
        self.offset = f.tell()
        f.write(self)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'ClipHeader (offset: {self.offset})')
        print(pad + f'  num_bones: {self.num_bones}')
        print(pad + f'  num_segments: {self.num_segments}')
        print(pad + f'  rotation_format: {ClipHeader.ROTATION_FORMAT[self.rotation_format]}')
        print(pad + f'  translation_format: {ClipHeader.VECTOR_FORMAT[self.translation_format]}')
        print(pad + f'  scale_format: {ClipHeader.VECTOR_FORMAT[self.scale_format]}')
        print(pad + f'  clip_range_reduction: {self.get_clip_range_reduction()}')
        print(pad + f'  segment_range_reduction: {self.get_segment_range_reduction()}')
        print(pad + f'  has_scale: {self.has_scale > 0}')
        print(pad + f'  default_scale: {self.default_scale > 0}')
        print(pad + f'  num_samples: {self.num_samples}')
        print(pad + f'  sample_rate (fps): {self.sample_rate}')
        print(pad + f'  segment_headers_offset: {self.segment_headers_offset}')
        print(pad + f'  default_tracks_bitset_offset: {self.default_tracks_bitset_offset}')
        print(pad + f'  constant_tracks_bitset_offset: {self.constant_tracks_bitset_offset}')
        print(pad + f'  constant_tracks_data_offset: {self.constant_tracks_data_offset}')
        print(pad + f'  clip_range_data_offset: {self.clip_range_data_offset}')

    def get_default_tracks_bitset_size(self):
        """Get size of default tracks bitset."""
        return self.constant_tracks_bitset_offset - self.default_tracks_bitset_offset

    def get_constant_tracks_bitset_size(self):
        """Get size of constant tracks bitset."""
        return self.constant_tracks_data_offset - self.constant_tracks_bitset_offset

    def get_constant_tracks_data_size(self):
        """Get size of constant tracks data."""
        return self.clip_range_data_offset - self.constant_tracks_data_offset

    def get_clip_range_reduction(self):
        """Get clip_range_reduction as a string."""
        return ClipHeader.RANGE_REDUCTION_FLAGS[self.clip_range_reduction]

    def set_clip_range_reduction(self, range_reduction_option):
        """Set clip_range_reduction with a string."""
        self.clip_range_reduction = ClipHeader.RANGE_REDUCTION_FLAGS.index(range_reduction_option)

    def get_segment_range_reduction(self):
        """Get segment_range_reduction as a string."""
        return ClipHeader.RANGE_REDUCTION_FLAGS[self.segment_range_reduction]

    def set_segment_range_reduction(self, range_reduction_option):
        """Set segment_range_reduction with a string."""
        self.segment_range_reduction = ClipHeader.RANGE_REDUCTION_FLAGS.index(range_reduction_option)


class SegmentHeader(c.LittleEndianStructure):
    """Compressed clip segment header."""
    _pack_ = 1
    _fields_ = [
        ("num_samples", c.c_uint32),
        ("animated_pose_bit_size", c.c_int32),
        ("format_per_track_data_offset", c.c_int32),
        ("range_data_offset", c.c_int32),
        ("track_data_offset", c.c_int32),
    ]

    @staticmethod
    def read(f):
        """Read function."""
        header = SegmentHeader()
        header.offset = f.tell()
        f.readinto(header)
        return header

    def write(self, f):
        """Write function."""
        self.offset = f.tell()
        f.write(self)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'SegmentHeader (offset: {self.offset})')
        print(pad + f'  num_samples: {self.num_samples}')
        print(pad + f'  animated_pose_bit_size: {self.animated_pose_bit_size}')
        print(pad + f'  format_per_track_data_offset: {self.format_per_track_data_offset}')
        print(pad + f'  range_data_offset: {self.range_data_offset}')
        print(pad + f'  track_data_offset: {self.track_data_offset}')


class Segment:
    """Compressed clip segment."""

    BIT_RATE_NUM_BITS = [
        0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 32
    ]

    def __init__(self, offset, bit_rates, segment_range_data, track_data):
        """Constructor."""
        self.offset = offset
        self.bit_rates = bit_rates
        self.segment_range_data = segment_range_data
        self.track_data = track_data

    @staticmethod
    def read(f, clip_header, segment_header, range_count):
        """Read function."""
        offset = f.tell()
        # read bit rates
        if range_count != 0:
            io.check(f.tell(), segment_header.format_per_track_data_offset + clip_header.offset)
        bit_rates = io.read_uint8_array(f, length=range_count)
        bit_rates = [Segment.BIT_RATE_NUM_BITS[i] for i in bit_rates]
        num_padding = (2 - f.tell() + clip_header.offset) % 2
        io.check(f.read(num_padding), b'\xcd' * num_padding)  # padding

        # read segment range data
        if clip_header.get_segment_range_reduction() == 'AllTracks':
            io.check(f.tell(), segment_header.range_data_offset + clip_header.offset)
            segment_range_data = [RangeData.read(f, segment=True) for i in range(range_count)]
        else:
            segment_range_data = []
        num_padding = (4 - f.tell() + clip_header.offset) % 4
        io.check(f.read(num_padding), b'\xcd' * num_padding)  # padding

        # read animated track data
        track_data_size = sum(bit_rates) * 3
        num_samples = segment_header.num_samples
        length = math.ceil(track_data_size * num_samples / 8)
        if range_count != 0:
            io.check(f.tell(), segment_header.track_data_offset + clip_header.offset)
        track_data = io.read_uint8_array(f, length)

        return Segment(offset, bit_rates, segment_range_data, track_data)

    def decompress(self, clip_header, segment_header, clip_range_data, range_count, bone_track_floats):
        """Unpack animated track data."""
        num_samples = segment_header.num_samples
        clip_range_reduction = clip_header.get_clip_range_reduction()
        segment_range_reduction = clip_header.get_segment_range_reduction()
        track_data_size = sum(self.bit_rates) * 3
        binary = ''
        for i in self.track_data:
            binary += format(i, "b").zfill(8)

        def get_frame_bin(i, binary, track_data_size, idx, bits):
            return binary[i * track_data_size + idx: i * track_data_size + idx + bits * 3]
        idx = 0
        bone_track_floats = [[] for i in range(range_count)]
        for bits, rid in zip(self.bit_rates, range(range_count)):
            if bits != 0:
                bone_track_bin = [get_frame_bin(i, binary, track_data_size, idx, bits) for i in range(num_samples)]
                bone_track_bin = [[b[i * bits: (i + 1) * bits] for i in range(3)] for b in bone_track_bin]
                bone_track_bin = sum(bone_track_bin, [])
                max_int = (1 << bits) - 1
                ints = [int(b, 2) for b in bone_track_bin]
            else:
                max_int = (1 << 16) - 1
                const_vec = self.segment_range_data[rid].convert_to_vec3_i16()
                ints = const_vec * num_samples
            if bits != 32:
                floats = [i / max_int for i in ints]
                xyzs = [floats[i * 3: (i + 1) * 3] for i in range(num_samples)]
                if bits != 0 and segment_range_reduction == 'AllTracks':
                    srd = self.segment_range_data[rid]
                    xyzs = [srd.unpack(xyz) for xyz in xyzs]
                if clip_range_reduction == 'AllTracks':
                    rd = clip_range_data[rid]
                    xyzs = [rd.unpack(xyz) for xyz in xyzs]
            else:
                bt = [i.to_bytes(4, byteorder="big") for i in ints]
                floats = [struct.unpack('>f', b)[0] for b in bt]
                xyzs = [floats[i * 3: (i + 1) * 3] for i in range(num_samples)]

            bone_track_floats[rid] = xyzs
            idx += bits * 3
        self.decompressed_track_data = bone_track_floats

    def write(self, f, clip_header, segment_header):
        """Write function."""
        segment_header.animated_pose_bit_size = sum(self.bit_rates) * 3
        segment_header.format_per_track_data_offset = f.tell() - clip_header.offset
        bit_rates = [Segment.BIT_RATE_NUM_BITS.index(i) for i in self.bit_rates]
        io.write_uint8_array(f, bit_rates)
        num_padding = (2 - f.tell() + clip_header.offset) % 2
        f.write(b'\xcd' * num_padding)

        segment_header.range_data_offset = f.tell() - clip_header.offset
        list(map(lambda x: x.write(f, segment=True), self.segment_range_data))
        num_padding = (4 - f.tell() + clip_header.offset) % 4
        f.write(b'\xcd' * num_padding)  # padding

        segment_header.track_data_offset = f.tell() - clip_header.offset
        io.write_uint8_array(f, self.track_data)
        if len(bit_rates) == 0:
            segment_header.format_per_track_data_offset = -1
            segment_header.track_data_offset = -1
        if clip_header.get_segment_range_reduction() != 'AllTracks':
            segment_header.range_data_offset = -1

    def disable_range_reduction(self):
        """Disable range reduction."""
        if len(self.bit_rates) == 0:
            return
        self.segment_range_data = []
        dtd = self.decompressed_track_data
        self.bit_rates = [32] * len(dtd)
        track_data = sum(sum([[dtd[i][t] for i in range(len(dtd))] for t in range(len(dtd[0]))], []), [])
        self.track_data = struct.pack('>' + 'f' * len(track_data), *track_data)
        self.track_data = struct.unpack('<' + 'B' * len(self.track_data), self.track_data)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'Segment (offset: {self.offset})')


class RangeData:
    """Range data for range reduction."""

    def __init__(self, min_xyz, extent_xyz):
        """Constructor."""
        self.min_xyz = min_xyz
        self.extent_xyz = extent_xyz

    @staticmethod
    def read(f, segment=False):
        """Read function."""
        if segment:
            min_xyz = io.read_vec3_i8(f)
            extent_xyz = io.read_vec3_i8(f)
        else:
            min_xyz = io.read_vec3_f32(f)
            extent_xyz = io.read_vec3_f32(f)
        range_data = RangeData(min_xyz, extent_xyz)
        return range_data

    def write(self, f, segment=False):
        """Write function."""
        if segment:
            io.write_vec3_i8(f, self.min_xyz)
            io.write_vec3_i8(f, self.extent_xyz)
        else:
            io.write_vec3_f32(f, self.min_xyz)
            io.write_vec3_f32(f, self.extent_xyz)

    @staticmethod
    def unpack_elem(elem, range_min, range_extent):
        """Unpack a normalized value."""
        return elem * range_extent + range_min

    def unpack(self, xyz):
        """Unpack a normalized vector."""
        vec = [RangeData.unpack_elem(i, m, e) for i, m, e in zip(xyz, self.min_xyz, self.extent_xyz)]
        return vec

    def print(self):
        """Print meta data."""
        print(self.min_xyz)
        print(self.extent_xyz)

    def convert_to_vec3_i16(self):
        """Use range data as a vector."""
        i8_list = [int(x * 255) for x in self.min_xyz + self.extent_xyz]
        i16_vec3 = [i8_list[i * 2] * 256 + i8_list[i * 2 + 1] for i in range(3)]
        return i16_vec3


class BoneTrack:
    """Animation track for a bone."""

    def __init__(self):
        """Constructor."""
        self.use_default = [False] * 3
        self.use_constant = [False] * 3
        self.constant_list = []
        self.track_data = []

    def set_use_default(self, use_default_str):
        """Set use_default by a string (e.g. '001')."""
        self.use_default = [flag == '1' for flag in use_default_str]
        if len(use_default_str) != 3:
            self.use_default += [True]

    def set_use_constant(self, use_constant_str):
        """Set use_constant by a string (e.g. '001')."""
        self.use_constant = [flag == '1' for flag in use_constant_str]
        if len(use_constant_str) != 3:
            self.use_constant += [True]

    def set_constants(self, constant_tracks_data, constant_id):
        """Set constants for tracks."""
        constant_count = self.get_constant_count()
        self.constant_list = constant_tracks_data[constant_id: constant_id + constant_count]
        return constant_count

    def get_constant_count(self):
        """Get how many constants it needs."""
        return sum(1 for f1, f2 in zip(self.use_default, self.use_constant) if (not f1) and f2) * 3

    def get_range_count(self):
        """Get how many range reductions it needs."""
        return 3 - sum(self.use_constant)

    def set_track_data(self, floats, offset):
        """Set track data."""
        range_count = self.get_range_count()
        track_data = floats[offset: offset + range_count]
        self.track_data = track_data
        return range_count

    def import_track(self, track_data):
        """Import bone track."""
        track_data = [track_data.rot, track_data.trans, track_data.scale]
        self.use_default = [len(x) == 0 for x in track_data]
        self.use_constant = [len(x) <= 1 for x in track_data]
        self.constant_list = sum([x[0] for x in track_data if len(x) == 1], [])
        self.track_data = [x for x in track_data if len(x) > 1]

    def print(self, name='', padding=4):
        """Print meta data."""
        def flag_to_str(f1, f2):
            if f1:
                return 'Default'
            if f2:
                return 'Constant'
            return 'Range reduction'
        string = [flag_to_str(f1, f2) for f1, f2 in zip(self.use_default, self.use_constant)]
        pad = ' ' * padding
        print(pad + f'{name}')
        print(pad + f'  Rotation: {string[0]}')
        print(pad + f'  Translation: {string[1]}')
        print(pad + f'  Scale: {string[2]}')


class CompressedClip:
    """Compressed clip for ACL."""
    def __init__(self, offset, size, data_hash, clip_header, segment_headers,
                 range_data, segments, bone_tracks):
        """Constructor."""
        self.offset = offset
        self.size = size
        self.data_hash = data_hash
        self.clip_header = clip_header
        self.segment_headers = segment_headers
        self.range_data = range_data
        self.segments = segments
        self.bone_tracks = bone_tracks

    # Todo: optimize this awful function
    @staticmethod
    def read(f):
        """Read function."""
        offset = f.tell()
        size = io.read_uint32(f)
        data_hash = f.read(4)

        # https://github.com/nfrechette/acl/blob/develop/includes/acl/core/buffer_tag.h
        # b'\x10\xac\x10\xac': compressed_clip (pre-2.0 file format.)
        # b'\x11\xac\x11\xac': compressed_tracks
        # b'\x01\xdb\x11\xac': compressed_database
        buffer_tag = f.read(4)
        io.check(buffer_tag, b'\x10\xac\x10\xac', msg='Unsupported ACL format.')

        # https://github.com/nfrechette/acl/blob/develop/includes/acl/core/compressed_tracks_version.h
        # 3: ACL v1.1.0
        io.check(io.read_uint16(f), 3, msg='Unsupported ACL version.')

        # https://github.com/nfrechette/acl/blob/develop/includes/acl/core/algorithm_types.h
        # 0: uniformly sampled
        io.check(io.read_uint8(f), 0)
        io.check(io.read_uint8(f), 0)  # padding

        # read headers
        clip_header = ClipHeader.read(f)
        segment_headers = io.read_array(f, SegmentHeader.read, length=clip_header.num_segments)

        # check formats
        clip_range_reduction = clip_header.get_clip_range_reduction()
        if clip_range_reduction not in ['None', 'AllTracks']:
            raise RuntimeError(f"Unsupported animation clip (clip range reduction: {clip_range_reduction})")
        segment_range_reduction = clip_header.get_segment_range_reduction()
        if segment_range_reduction not in ['None', 'AllTracks']:
            raise RuntimeError(f"Unsupported animation clip (segment range reduction: {segment_range_reduction})")
        rot_format = ClipHeader.ROTATION_FORMAT[clip_header.rotation_format]
        trans_format = ClipHeader.VECTOR_FORMAT[clip_header.translation_format]
        scale_format = ClipHeader.VECTOR_FORMAT[clip_header.scale_format]
        if rot_format != 'QuatDropW_Variable':
            raise RuntimeError(f"Unsupported animation clip (rotation format: {rot_format})")
        if trans_format != 'Vector3_Variable':
            raise RuntimeError(f"Unsupported animation clip (translation format: {trans_format})")
        if scale_format != 'Vector3_Variable':
            raise RuntimeError(f"Unsupported animation clip (scale format: {scale_format})")
        if clip_header.default_scale != 1:
            raise RuntimeError(f"Unsupported animation clip (default scale: {clip_header.default_scale})")

        # read bit sets
        num_attributes = 2 + clip_header.has_scale
        default_tracks_bitset = io.read_uint32_array(f, length=clip_header.get_default_tracks_bitset_size() // 4)
        constant_tracks_bitset = io.read_uint32_array(f, length=clip_header.get_constant_tracks_bitset_size() // 4)

        def get_tracks_flags(bitset, num_bones, num_attributes):
            tracks_flags = ''
            for i in bitset:
                tracks_flags += format(i, "b").zfill(32)
            tracks_flags = tracks_flags[: num_bones * num_attributes]
            return tracks_flags

        default_tracks_flags = get_tracks_flags(default_tracks_bitset, clip_header.num_bones, num_attributes)
        constant_tracks_flags = get_tracks_flags(constant_tracks_bitset, clip_header.num_bones, num_attributes)

        # read constant tracks
        constant_tracks_data = io.read_float32_array(f, length=clip_header.get_constant_tracks_data_size() // 4)

        constant_count = 0
        range_count = 0
        bone_tracks = [BoneTrack() for i in range(clip_header.num_bones)]
        for track, i in zip(bone_tracks, range(clip_header.num_bones)):
            track.set_use_default(default_tracks_flags[i * num_attributes: (i + 1) * num_attributes])
            track.set_use_constant(constant_tracks_flags[i * num_attributes: (i + 1) * num_attributes])
            constant_count += track.set_constants(constant_tracks_data, constant_count)
            range_count += track.get_range_count()

        # read clip range data
        io.check(f.tell(), clip_header.clip_range_data_offset + clip_header.offset)
        if clip_range_reduction == 'AllTracks':
            range_data = io.read_array(f, RangeData.read, length=range_count)
        else:
            range_data = []

        # read segments
        bone_track_floats = [[] for i in range(range_count)]
        segments = []
        for s_header in segment_headers:
            seg = Segment.read(f, clip_header, s_header, range_count)
            seg.decompress(clip_header, s_header, range_data, range_count, bone_track_floats)
            segments.append(seg)

        for seg in segments:
            for btf, dtd in zip(bone_track_floats, seg.decompressed_track_data):
                btf += dtd

        # set unpacked data
        idx = 0
        for track in bone_tracks:
            idx += track.set_track_data(bone_track_floats, idx)

        io.check(idx, len(bone_track_floats))

        io.check(f.read(15), b'\xcd' * 15)
        io.check(f.tell() - offset, size)
        return CompressedClip(offset, size, data_hash, clip_header, segment_headers,
                              range_data, segments, bone_tracks)

    def write(self, f):
        """Write function."""
        offset = f.tell()
        io.write_uint32(f, self.size)
        f.write(self.data_hash)
        f.write(b'\x10\xac\x10\xac')
        io.write_uint32(f, 3)
        self.clip_header.write(f)
        self.clip_header.segment_headers_offset = f.tell() - self.clip_header.offset
        list(map(lambda x: x.write(f), self.segment_headers))
        num_attributes = 2 + self.clip_header.has_scale
        self.clip_header.default_tracks_bitset_offset = f.tell() - self.clip_header.offset
        use_default = sum([track.use_default[:num_attributes] for track in self.bone_tracks], [])
        use_default = ["1" if flag else "0" for flag in use_default] + ["0"] * ((32 - len(use_default)) % 32)
        use_default = [use_default[i * 32: (i + 1) * 32] for i in range(len(use_default) // 32)]
        default_tracks_bitset = [int(''.join(b), 2) for b in use_default]
        io.write_uint32_array(f, default_tracks_bitset)
        self.clip_header.constant_tracks_bitset_offset = f.tell() - self.clip_header.offset
        use_constant = sum([track.use_constant[:num_attributes] for track in self.bone_tracks], [])
        use_constant = ["1" if flag else "0" for flag in use_constant] + ["0"] * ((32 - len(use_constant)) % 32)
        use_constant = [use_constant[i * 32: (i + 1) * 32] for i in range(len(use_constant) // 32)]
        constant_tracks_bitset = [int(''.join(b), 2) for b in use_constant]
        io.write_uint32_array(f, constant_tracks_bitset)
        self.clip_header.constant_tracks_data_offset = f.tell() - self.clip_header.offset
        constant_tracks_data = sum([track.constant_list for track in self.bone_tracks], [])
        io.write_float32_array(f, constant_tracks_data)
        self.clip_header.clip_range_data_offset = f.tell() - self.clip_header.offset
        list(map(lambda x: x.write(f), self.range_data))
        io.rewrite_struct(f, self.clip_header)
        list(map(lambda head, seg: seg.write(f, self.clip_header, head), self.segment_headers, self.segments))
        list(map(lambda x: io.rewrite_struct(f, x), self.segment_headers))
        f.write(b'\xcd' * 15)
        end_offset = f.tell()
        self.size = end_offset - offset
        f.seek(offset)
        io.write_uint32(f, self.size)
        f.seek(end_offset)

    def disable_range_reduction(self):
        """Disable renge reduction."""
        self.clip_header.set_clip_range_reduction('None')
        self.clip_header.set_segment_range_reduction('None')
        self.range_data = []
        for seg in self.segments:
            seg.disable_range_reduction()

    def import_anim_data(self, anim_data):
        """Import animation data."""
        for acl_track, blender_track in zip(self.bone_tracks, anim_data):
            acl_track.import_track(blender_track)
        range_count = sum(track.get_range_count() for track in self.bone_tracks)
        self.clip_header.num_segments = 1
        self.clip_header.has_scale = 1
        new_seg_header = SegmentHeader()
        new_seg_header.num_samples = self.clip_header.num_samples
        new_segment = Segment(0, [32] * range_count, [], b'')
        new_segment.decompressed_track_data = sum([track.track_data for track in self.bone_tracks], [])
        self.segment_headers = [new_seg_header]
        self.segments = [new_segment]
        self.disable_range_reduction()

    def print(self):
        """Print meta data."""
        print(f'CompressedClip (offset: {self.offset})')
        print('  ACL version: 1.1.0')
        print(f'  size: {self.size}')
        self.clip_header.print()
        for seg in self.segment_headers:
            seg.print()
        for seg in self.segments:
            seg.print()
