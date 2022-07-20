"""Classes for ACL data.

Notes:
    Only supports ACL v1.1.0.
    https://github.com/nfrechette/acl/blob/v1.1.0/includes/acl/core/compressed_clip.h
"""
import ctypes as c
import math
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

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'ClipHeader (offset: {self.offset})')
        print(pad + f'  num_bones: {self.num_bones}')
        print(pad + f'  num_segments: {self.num_segments}')
        print(pad + f'  rotation_format: {ClipHeader.ROTATION_FORMAT[self.rotation_format]}')
        print(pad + f'  translation_format: {ClipHeader.VECTOR_FORMAT[self.translation_format]}')
        print(pad + f'  scale_format: {ClipHeader.VECTOR_FORMAT[self.scale_format]}')
        print(pad + f'  clip_range_reduction: {ClipHeader.RANGE_REDUCTION_FLAGS[self.clip_range_reduction]}')
        print(pad + f'  segment_range_reduction: {ClipHeader.RANGE_REDUCTION_FLAGS[self.segment_range_reduction]}')
        print(pad + f'  has_scale: {self.has_scale > 0}')
        print(pad + f'  num_samples: {self.num_samples}')
        print(pad + f'  sample_rate (fps): {self.sample_rate}')

    def get_default_tracks_bitset_size(self):
        """Get size of default tracks bitset."""
        return self.constant_tracks_bitset_offset - self.default_tracks_bitset_offset

    def get_constant_tracks_bitset_size(self):
        """Get size of constant tracks bitset."""
        return self.constant_tracks_data_offset - self.constant_tracks_bitset_offset

    def get_constant_tracks_data_size(self):
        """Get size of constant tracks data."""
        return self.clip_range_data_offset - self.constant_tracks_data_offset


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

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'SegmentHeader (offset: {self.offset})')
        print(pad + f'  num_samples: {self.num_samples}')
        print(pad + f'  animated_pose_bit_size: {self.animated_pose_bit_size}')
        print(pad + f'  format_per_track_data_offset: {self.format_per_track_data_offset}')
        print(pad + f'  range_data_offset: {self.range_data_offset}')
        print(pad + f'  track_data_offset: {self.track_data_offset}')


class RangeData:
    """Range data for range reduction."""

    def __init__(self, min_xyz, extent_xyz):
        """Constructor."""
        self.min_xyz = min_xyz
        self.extent_xyz = extent_xyz

    @staticmethod
    def read(f):
        """Read function."""
        min_xyz = io.read_vec3_f32(f)
        extent_xyz = io.read_vec3_f32(f)
        range_data = RangeData(min_xyz, extent_xyz)
        return range_data

    def write(self, f):
        """Write function."""
        io.write_vec3_f32(f, self.min_xyz)
        io.write_vec3_f32(f, self.extent_xyz)

    @staticmethod
    def unpack_elem(elem, range_min, range_extent):
        """Unpack a normalized value."""
        return elem * range_extent + range_min

    def unpack(self, xyz):
        """Unpack a normalized vector."""
        return [RangeData.unpack_elem(i, m, e) for i, m, e in zip(xyz, self.min_xyz, self.extent_xyz)]

    def print(self):
        """Print meta data."""
        print(self.min_xyz)
        print(self.extent_xyz)


class BoneTrack:
    """Animation track for a bone."""

    def __init__(self):
        """Constructor."""
        self.use_default = [False] * 3
        self.use_constant = [False] * 3
        self.constant_list = []
        self.range_list = []
        self.bit_rates = []
        self.track_data_list = []

    def set_use_default(self, use_default_str):
        """Set use_default by a string (e.g. '001')."""
        self.use_default = [flag == '1' for flag in use_default_str]

    def set_use_constant(self, use_constant_str):
        """Set use_constant by a string (e.g. '001')."""
        self.use_constant = [flag == '1' for flag in use_constant_str]

    def set_constants(self, constant_tracks_data, constant_id):
        """Set constants for tracks."""
        constant_count = self.get_constant_count()
        self.constant_list = constant_tracks_data[constant_id: constant_id + constant_count]
        return constant_count

    def set_ranges(self, range_data, bit_rates, range_id):
        """Set ranges for tracks."""
        range_count = self.get_range_count()
        self.range_list = range_data[range_id: range_id + range_count]
        self.bit_rates = bit_rates[range_id: range_id + range_count]
        return range_count

    def get_constant_count(self):
        """Get how many constants it needs."""
        return sum(1 for f1, f2 in zip(self.use_default, self.use_constant) if (not f1) and f2) * 3

    def get_range_count(self):
        """Get how many range reductions it needs."""
        return 3 - sum(self.use_constant)

    def get_track_data_size(self):
        """Get binary size for valiable tracks."""
        return sum(bits for bits in self.bit_rates) * 3

    def set_track_data(self, track_data_bin_, track_data_id):
        """Set track data."""
        num_samples = len(track_data_bin_)
        frame_size = sum(bits for bits in self.bit_rates)
        track_data_size = frame_size * 3
        track_data_bin = [b[track_data_id: track_data_id + track_data_size] for b in track_data_bin_]
        track_data = []
        offset = 0
        for bit_rate, range_data in zip(self.bit_rates, self.range_list):
            frame_data_bin = ''.join([b[offset: offset + bit_rate * 3] for b in track_data_bin])
            binary = [frame_data_bin[i * bit_rate: (i + 1) * bit_rate] for i in range(3 * num_samples)]
            print(binary)
            max_int = (1 << bit_rate) - 1
            ints = [int(b, 2) for b in binary]
            floats = [i / max_int for i in ints]
            # print(max(floats))
            xyzs = [floats[i * 3: (i + 1) * 3] for i in range(num_samples)]
            xyzs = [range_data.unpack(xyz) for xyz in xyzs]
            track_data.append(xyzs)
            offset += bit_rate * 3
        self.track_data = track_data
        return track_data_size

    def print(self, name, padding=4):
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

    BIT_RATE_NUM_BITS = [
        0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 32
    ]

    def __init__(self, offset, size, data_hash, clip_header, segment_headers,
                 default_tracks_bitset, constant_tracks_bitset,
                 range_data, bit_rates, track_data, bone_tracks):
        """Constructor."""
        self.offset = offset
        self.size = size
        self.data_hash = data_hash
        self.clip_header = clip_header
        self.segment_headers = segment_headers
        self.default_tracks_bitset = default_tracks_bitset
        self.constant_tracks_bitset = constant_tracks_bitset
        self.range_data = range_data
        self.bit_rates = bit_rates
        self.track_data = track_data
        self.bone_tracks = bone_tracks

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

        clip_header = ClipHeader.read(f)
        if clip_header.has_scale == 0:
            raise RuntimeError("Unsupported animation clip (no scale data)")
        clip_range_reduction = ClipHeader.RANGE_REDUCTION_FLAGS[clip_header.clip_range_reduction]
        if clip_range_reduction != 'AllTracks':
            raise RuntimeError(f"Unsupported animation clip (clip range reduction: {clip_range_reduction})")
        segment_range_reduction = ClipHeader.RANGE_REDUCTION_FLAGS[clip_header.segment_range_reduction]
        if segment_range_reduction != 'None':
            raise RuntimeError(f"Unsupported animation clip (segment range reduction: {segment_range_reduction})")

        segment_headers = io.read_array(f, SegmentHeader.read, length=clip_header.num_segments)
        default_tracks_bitset = io.read_uint32_array(f, length=clip_header.get_default_tracks_bitset_size() // 4)
        constant_tracks_bitset = io.read_uint32_array(f, length=clip_header.get_constant_tracks_bitset_size() // 4)
        bone_tracks = [BoneTrack() for i in range(clip_header.num_bones)]

        def get_tracks_flags(bitset, num_bones):
            tracks_flags = ''
            for i in bitset:
                tracks_flags += format(i, "b").zfill(32)
            tracks_flags = tracks_flags[: num_bones * 3]
            return tracks_flags

        default_tracks_flags = get_tracks_flags(default_tracks_bitset, clip_header.num_bones)
        constant_tracks_flags = get_tracks_flags(constant_tracks_bitset, clip_header.num_bones)
        constant_tracks_data = io.read_float32_array(f, length=clip_header.get_constant_tracks_data_size() // 4)

        constant_count = 0
        range_count = 0
        for track, i in zip(bone_tracks, range(clip_header.num_bones)):
            track.set_use_default(default_tracks_flags[i * 3: (i + 1) * 3])
            track.set_use_constant(constant_tracks_flags[i * 3: (i + 1) * 3])
            constant_count += track.set_constants(constant_tracks_data, constant_count)
            range_count += track.get_range_count()

        range_data = io.read_array(f, RangeData.read, length=range_count)
        bit_rates = io.read_uint8_array(f, length=range_count)
        bit_rates = [CompressedClip.BIT_RATE_NUM_BITS[i] for i in bit_rates]
        io.check(f.read(2), b'\xcd\xcd')  # padding

        range_count = 0
        track_data_size = 0
        for track, i in zip(bone_tracks, range(clip_header.num_bones)):
            range_count += track.set_ranges(range_data, bit_rates, range_count)
            track_data_size += track.get_track_data_size()

        track_data = io.read_uint32_array(f, length=math.ceil(track_data_size * clip_header.num_samples / 32))

        binary = ''
        for i in track_data:
            binary += format(i, "b").zfill(32)

        track_data_id = 0
        num_samples = clip_header.num_samples
        track_data_bin = [binary[i * track_data_size: (i + 1) * track_data_size] for i in range(num_samples)]
        for track in bone_tracks:
            track_data_id += track.set_track_data(track_data_bin, track_data_id)

        return CompressedClip(offset, size, data_hash, clip_header, segment_headers,
                              default_tracks_bitset, constant_tracks_bitset,
                              range_data, bit_rates, track_data, bone_tracks)

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.size)
        f.write(self.data_hash)
        f.write(b'\x10\xac\x10\xac')
        io.write_uint32(f, 3)
        f.write(self.clip_header)
        io.write_struct_array(f, self.segment_headers)
        io.write_uint32_array(f, self.default_tracks_bitset)
        io.write_uint32_array(f, self.constant_tracks_bitset)
        constant_tracks_data = sum([track.constant_list for track in self.bone_tracks], [])
        io.write_float32_array(f, constant_tracks_data)
        list(map(lambda x: x.write(f), self.range_data))
        bit_rates = [CompressedClip.BIT_RATE_NUM_BITS.index(i) for i in self.bit_rates]
        io.write_uint8_array(f, bit_rates)
        f.write(b'\xcd\xcd')
        io.write_uint32_array(f, self.track_data)

    def print(self, bone_names):
        """Print meta data."""
        print(f'CompressedClip (offset: {self.offset})')
        print('  ACL version: 1.1.0')
        print(f'  size: {self.size}')
        self.clip_header.print()
        for seg in self.segment_headers:
            seg.print()
        print('  Track Settings')
        for track, name in zip(self.bone_tracks, bone_names):
            track.print(name)
