"""Class for texture asset."""
import os
from ..util import io_util as io
from .mipmap import Mipmap

# classes for texture assets (.uexp and .ubulk)

BYTE_PER_PIXEL = {
    'DXT1/BC1': 0.5,
    'DXT5/BC3': 1,
    'BC4/ATI1': 0.5,
    'BC4(signed)': 0.5,
    'BC5/ATI2': 1,
    'BC5(signed)': 1,
    'BC6H(unsigned)': 1,
    'BC6H(signed)': 1,
    'BC7': 1,
    'FloatRGBA': 8,
    'B8G8R8A8': 4
}

PF_FORMAT = {
    'PF_DXT1': 'DXT1/BC1',
    'PF_DXT5': 'DXT5/BC3',
    'PF_BC4': 'BC4/ATI1',
    'PF_BC5': 'BC5/ATI2',
    'PF_BC6H': 'BC6H(unsigned)',
    'PF_BC7': 'BC7',
    'PF_FloatRGBA': 'FloatRGBA',
    'PF_B8G8R8A8': 'B8G8R8A8'
}


def is_power_of_2(num):
    """The number is a power of 2 or not."""
    if num == 1:
        return True
    if num % 2 != 0:
        return False
    return is_power_of_2(num // 2)


# get all file paths for texture asset from a file path.
EXT = ['.uasset', '.uexp', '.ubulk']


def get_all_file_path(file):
    """Get .uasset, .uexp, and .ubulk paths."""
    base_name, ext = os.path.splitext(file)
    if ext not in EXT:
        raise RuntimeError(f'Not Uasset. ({file})')
    return [base_name + ext for ext in EXT]


VERSION_ERR_MSG = 'Make sure you specified UE4 version correctly.'


class Texture:
    """Class for texture asset."""
    UNREAL_SIGNATURE = b'\xC1\x83\x2A\x9E'
    UBULK_FLAG = [0, 16384]

    @staticmethod
    def read(f, uasset, verbose=False):
        """Read function."""
        return Texture(f, uasset, verbose=verbose)

    def __init__(self, f, uasset, verbose=False):
        """Load .uexp and .ubulk."""
        self.uasset = uasset
        version = self.uasset.version

        file_path = f.name

        _, _, ubulk_name = get_all_file_path(file_path)

        self.version = version

        if len(self.uasset.exports) != 1:
            raise RuntimeError('Unexpected number of exports')

        self.uasset_size = self.uasset.size
        self.name_list = self.uasset.name_list
        self.texture_type = '2D' if self.uasset.asset_type == 'Texture2D' else 'Cube'

        # read .uexp
        self.read_uexp(f)

        # read .ubulk
        if self.has_ubulk:
            with open(ubulk_name, 'rb') as bulk_f:
                size = io.get_size(bulk_f)
                for mip in self.mipmaps:
                    if mip.uexp:
                        continue
                    mip.data = bulk_f.read(mip.data_size)
                io.check(size, bulk_f.tell())

        if verbose:
            self.print()

    def read_uexp(self, f):
        """Read .uexp."""
        # read cooked size if exist
        self.bin1 = None
        self.imported_width = None
        self.imported_height = None
        if self.uasset.unversioned:
            unv_head = io.read_uint8_array(f, 2)
            is_last = unv_head[1] % 2 == 0
            while is_last:
                unv_head = io.read_uint8_array(f, 2)
                is_last = unv_head[1] % 2 == 0
                if f.tell() > 100:
                    raise RuntimeError('Parse Failed. ' + VERSION_ERR_MSG)
            size = f.tell()
            f.seek(0)
            self.bin1 = f.read(size)
            chk = io.read_uint8_array(f, 8)
            chk = [i for i in chk if i == 0]
            f.seek(-8, 1)
            if len(chk) > 2:
                self.imported_width = io.read_uint32(f)
                self.imported_height = io.read_uint32(f)
        else:
            first_property_id = io.read_uint64(f)
            if first_property_id >= len(self.name_list):
                raise RuntimeError('list index out of range. ' + VERSION_ERR_MSG)
            first_property = self.name_list[first_property_id]
            f.seek(0)
            if first_property == 'ImportedSize':
                self.bin1 = f.read(49)
                self.imported_width = io.read_uint32(f)
                self.imported_height = io.read_uint32(f)

        # skip property part
        offset = f.tell()
        binary = f.read(8)
        while binary != b'\x01\x00\x01\x00\x01\x00\x00\x00':
            binary = b''.join([binary[1:], f.read(1)])
            if f.tell() > 1000:
                raise RuntimeError('Parse Failed. ' + VERSION_ERR_MSG)
        size = f.tell() - offset
        f.seek(offset)
        self.unk = f.read(size)
        # read meta data
        self.type_name_id = io.read_uint64(f)
        self.offset_to_end_offset = f.tell()
        self.end_offset = io.read_uint32(f)  # Offset to end of uexp?
        if self.version >= '4.20':
            io.read_null(f, msg='Not NULL! ' + VERSION_ERR_MSG)
        if self.version == '5.0':
            io.read_null_array(f, 4)
        self.original_width = io.read_uint32(f)
        self.original_height = io.read_uint32(f)
        self.cube_flag = io.read_uint16(f)
        self.unk_int = io.read_uint16(f)
        if self.cube_flag == 1:
            if self.texture_type != '2D':
                raise RuntimeError('Unexpected error! Please report it to the developer.')
        elif self.cube_flag == 6:
            if self.texture_type != 'Cube':
                raise RuntimeError('Unexpected error! Please report it to the developer.')
        else:
            raise RuntimeError('Not a cube flag! ' + VERSION_ERR_MSG)
        self.type = io.read_str(f)
        if self.version == 'ff7r' and self.unk_int == Texture.UBULK_FLAG[1]:
            io.read_null(f)
            io.read_null(f)
            ubulk_map_num = io.read_uint32(f)  # bulk map num + unk_map_num
        self.unk_map_num = io.read_uint32(f)  # number of some mipmaps in uexp
        map_num = io.read_uint32(f)  # map num ?
        if self.version == 'ff7r':
            # ff7r has all mipmap data in a mipmap object
            self.uexp_mip_bulk = Mipmap.read(f, self.version)
            io.read_const_uint32(f, self.cube_flag)
            f.seek(4, 1)  # uexp mip map num

        # read mipmaps
        self.mipmaps = [Mipmap.read(f, self.version) for i in range(map_num)]
        _, ubulk_map_num = self.get_mipmap_num()
        self.has_ubulk = ubulk_map_num > 0

        # get format name
        if self.type not in PF_FORMAT:
            raise RuntimeError(f'Unsupported format. ({self.type})')
        self.format_name = PF_FORMAT[self.type]
        self.byte_per_pixel = BYTE_PER_PIXEL[self.format_name]

        if self.version == 'ff7r':
            # split mipmap data
            i = 0
            for mip in self.mipmaps:
                if mip.uexp:
                    size = int(mip.pixel_num * self.byte_per_pixel * self.cube_flag)
                    mip.data = self.uexp_mip_bulk.data[i: i + size]
                    i += size
            io.check(i, len(self.uexp_mip_bulk.data))

        if self.version >= '4.23':
            io.read_null(f, msg='Not NULL! ' + VERSION_ERR_MSG)
        # check(self.end_offset, f.tell()+self.uasset_size)
        self.none_name_id = io.read_uint64(f)

    def get_max_uexp_size(self):
        """Get max mip size for .uexp."""
        for mip in self.mipmaps:
            if mip.uexp:
                width, height = mip.width, mip.height
                break
        return width, height

    def get_max_size(self):
        """Get max mip size for .uexp and .ubulk."""
        return self.mipmaps[0].width, self.mipmaps[0].height

    def get_mipmap_num(self):
        """Get number of mipmaps."""
        uexp_map_num = 0
        ubulk_map_num = 0
        for mip in self.mipmaps:
            uexp_map_num += mip.uexp
            ubulk_map_num += not mip.uexp
        return uexp_map_num, ubulk_map_num

    def write(self, f):
        """Write .uexp and .ubulk."""
        file_path = f.name
        folder = os.path.dirname(file_path)
        if folder not in ['.', ''] and not os.path.exists(folder):
            io.mkdir(folder)

        _, _, ubulk_name = get_all_file_path(file_path)
        if not self.has_ubulk:
            ubulk_name = None

        # write .uexp
        self.write_uexp(f)

        # write .ubulk if exist
        if self.has_ubulk:
            with open(ubulk_name, 'wb') as bulk_f:
                for mip in self.mipmaps:
                    if not mip.uexp:
                        bulk_f.write(mip.data)

    def write_uexp(self, f, valid=False):
        """Write .uexp."""
        # get mipmap info
        max_width, max_height = self.get_max_size()
        uexp_map_num, ubulk_map_num = self.get_mipmap_num()
        uexp_map_data_size = 0
        for mip in self.mipmaps:
            if mip.uexp:
                uexp_map_data_size += len(mip.data) + 32 * (self.version != 'ff7r')

        # write cooked size if exist
        if self.bin1 is not None:
            f.write(self.bin1)

        if self.imported_height is not None:
            if not valid:
                self.imported_height = max(self.imported_height, self.original_height, max_height)
                self.imported_width = max(self.imported_width, self.original_width, max_width)
            io.write_uint32(f, self.imported_width)
            io.write_uint32(f, self.imported_height)

        if not valid:
            self.original_height = max_height
            self.original_width = max_width

        f.write(self.unk)

        # write meta data
        io.write_uint64(f, self.type_name_id)
        io.write_uint32(f, 0)  # write dummy offset. (rewrite it later)
        if self.version >= '4.20':
            io.write_null(f)
        if self.version == '5.0':
            io.write_null_array(f, 4)

        io.write_uint32(f, self.original_width)
        io.write_uint32(f, self.original_height)
        io.write_uint16(f, self.cube_flag)
        io.write_uint16(f, self.unk_int)

        io.write_str(f, self.type)

        if self.version == 'ff7r' and self.unk_int == Texture.UBULK_FLAG[1]:
            io.write_null(f)
            io.write_null(f)
            io.write_uint32(f, ubulk_map_num + self.unk_map_num)

        io.write_uint32(f, self.unk_map_num)
        io.write_uint32(f, len(self.mipmaps))

        if self.version == 'ff7r':
            # pack mipmaps in a mipmap object
            uexp_bulk = b''
            for mip in self.mipmaps:
                mip.meta = True
                if mip.uexp:
                    uexp_bulk = b''.join([uexp_bulk, mip.data])
            size = self.get_max_uexp_size()
            self.uexp_mip_bulk = Mipmap(self.version)
            self.uexp_mip_bulk.update(uexp_bulk, size, True)
            self.uexp_mip_bulk.offset = self.uasset_size + f.tell() + 24
            self.uexp_mip_bulk.write(f)

            io.write_uint32(f, self.cube_flag)
            io.write_uint32(f, uexp_map_num)

        # write mipmaps
        ubulk_offset = 0
        for mip in self.mipmaps:
            if mip.uexp:
                mip.offset = self.uasset_size + f.tell() + 24 - 4 * (self.version == '5.0')
            else:
                mip.offset = ubulk_offset
                ubulk_offset += mip.data_size
            mip.write(f)

        if self.version >= '4.25':
            io.write_null(f)

        if self.version == '5.0':
            new_end_offset = f.tell() - self.offset_to_end_offset
        else:
            new_end_offset = f.tell() + self.uasset_size
        io.write_uint64(f, self.none_name_id)

        if self.version < '4.26' and self.version != 'ff7r':
            base_offset = - self.uasset_size - f.tell()
            for mip in self.mipmaps:
                if not mip.uexp:
                    mip.offset += base_offset
                    mip.rewrite_offset(f)

        f.seek(self.offset_to_end_offset)
        io.write_uint32(f, new_end_offset)
        f.seek(0, 2)

    def remove_mipmaps(self):
        """Remove mipmaps except the largest one."""
        old_mipmap_num = len(self.mipmaps)
        if old_mipmap_num == 1:
            return
        self.mipmaps = [self.mipmaps[0]]
        self.mipmaps[0].uexp = True
        self.has_ubulk = False
        # print('mipmaps have been removed.')
        # print('  mipmap: {} -> 1'.format(old_mipmap_num))

    def inject_dds(self, dds, force=False):
        """Inject dds into asset."""
        # check formats
        if '(signed)' in dds.header.format_name:
            raise RuntimeError(f'UE4 requires unsigned format but your dds is {dds.header.format_name}.')

        if dds.header.format_name != self.format_name and not force:
            raise RuntimeError(f'The format does not match. ({self.type}, {dds.header.format_name})')

        if dds.header.texture_type != self.texture_type:
            msg = f'Texture type does not match. ({self.texture_type}, {dds.header.texture_type})'
            raise RuntimeError(msg)

        max_width, max_height = self.get_max_size()
        old_size = (max_width, max_height)
        old_mipmap_num = len(self.mipmaps)

        uexp_width, uexp_height = self.get_max_uexp_size()

        # inject
        i = 0
        self.mipmaps = [Mipmap(self.version) for i in range(len(dds.mipmap_data))]
        for data, size, mip in zip(dds.mipmap_data, dds.mipmap_size, self.mipmaps):
            if self.has_ubulk and i + 1 < len(dds.mipmap_data) and size[0] * size[1] > uexp_width * uexp_height:
                mip.update(data, size, False)
            else:
                mip.update(data, size, True)
            i += 1

        # print results
        max_width, max_height = self.get_max_size()
        new_size = (max_width, max_height)
        _, ubulk_map_num = self.get_mipmap_num()
        if ubulk_map_num == 0:
            self.has_ubulk = False
        if self.version == "ff7r":
            self.unk_int = Texture.UBULK_FLAG[self.has_ubulk]
        new_mipmap_num = len(self.mipmaps)

        print('dds has been injected.')
        print(f'  size: {old_size} -> {new_size}')
        print(f'  mipmap: {old_mipmap_num} -> {new_mipmap_num}')

        # warnings
        if new_mipmap_num > 1 and (not is_power_of_2(max_width) or not is_power_of_2(max_height)):
            msg = 'Warning: Mipmaps should have power of 2 as its width and height. '
            print(msg + f'({max_width}, {max_height})')
        if new_mipmap_num > 1 and old_mipmap_num == 1:
            print('Warning: The original texture has only 1 mipmap. But your dds has multiple mipmaps.')

    def print(self):
        """Print meta data."""
        for mip, i in zip(self.mipmaps, range(len(self.mipmaps))):
            print(f'Mipmap{i}')
            mip.print()

    def change_format(self, pixel_format):
        """Change pixel format."""
        if pixel_format not in PF_FORMAT:
            if pixel_format not in list(PF_FORMAT.values()):
                raise RuntimeError(f'Unsupported pixel format. ({pixel_format})')
            pixel_format = list(PF_FORMAT.keys())[list(PF_FORMAT.values()).index(pixel_format)]
        self.uasset.name_list[self.type_name_id] = pixel_format
        self.type = pixel_format
        self.format_name = PF_FORMAT[self.type]
