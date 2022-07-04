"""Class for mipmaps."""
import ctypes as c
from ..util import io_util as io


class Mipmap(c.LittleEndianStructure):
    """Mipmap class for texture asset."""
    _pack_ = 1
    _fields_ = [
        # ("one", c.c_uint32), #1
        ("ubulk_flag", c.c_uint16),  # 1281->ubulk, 72->uexp, 32 or 64->ff7r uexp
        ("unk_flag", c.c_uint16),  # ubulk and 1->ue4.27 or ff7r
        ("data_size", c.c_uint32),  # 0->ff7r uexp
        ("data_size2", c.c_uint32),  # data size again
        ("offset", c.c_uint64)
        # data, c_ubyte*
        # width, c_uint32
        # height, c_uint32
        # if version==4.27 or 20:
        #    null, c_uint32
    ]

    def __init__(self, version):
        """Constructor."""
        super().__init__()
        self.version = version

    def update(self, data, size, uexp):
        """Update attributes."""
        self.uexp = uexp
        self.meta = False
        self.data_size = len(data)
        self.data_size2 = len(data)
        self.data = data
        self.offset = 0
        self.width = size[0]
        self.height = size[1]
        self.pixel_num = self.width * self.height
        self.one = 1

    @staticmethod
    def read(f, version):
        """Read function."""
        mip = Mipmap(version)
        if version != '5.0':
            io.read_const_uint32(f, 1)
        f.readinto(mip)
        mip.uexp = mip.ubulk_flag not in [1025, 1281, 1]
        mip.meta = mip.ubulk_flag == 32
        if mip.uexp:
            mip.data = f.read(mip.data_size)

        mip.width = io.read_uint32(f)
        mip.height = io.read_uint32(f)
        if version >= '4.20':
            io.read_const_uint32(f, 1)

        io.check(mip.data_size, mip.data_size2)
        mip.pixel_num = mip.width * mip.height
        return mip

    def write(self, f):
        """Write function."""
        if self.uexp:
            if self.meta:
                self.ubulk_flag = 32
            else:
                self.ubulk_flag = 72 if self.version != 'ff7r' else 64
            self.unk_flag = 0
        else:
            self.ubulk_flag = 1281
            self.unk_flag = self.version > '4.26' or self.version == 'ff7r'
        if self.uexp and self.meta:
            self.data_size = 0
            self.data_size2 = 0

        if self.version != '5.0':
            io.write_uint32(f, 1)
        self.offset_to_offset_data = f.tell() + 12
        f.write(self)
        if self.uexp and not self.meta:
            f.write(self.data)
        io.write_uint32(f, self.width)
        io.write_uint32(f, self.height)
        if self.version >= '4.20':
            io.write_uint32(f, 1)

    def rewrite_offset(self, f):
        """Rewrite offset data."""
        current_offset = f.tell()
        f.seek(self.offset_to_offset_data)
        io.write_uint64(f, self.offset)
        f.seek(current_offset)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + 'file: ' + 'uexp' * self.uexp + 'ubluk' * (not self.uexp))
        print(pad + f'data size: {self.data_size}')
        print(pad + f'offset: {self.offset}')
        print(pad + f'width: {self.width}')
        print(pad + f'height: {self.height}')
