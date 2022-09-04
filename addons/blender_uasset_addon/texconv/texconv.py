"""Texture converter.

Notes:
    You need to download dll from https://github.com/matyalatte/Texconv-Custom-DLL.
    And put the dll in the same directory as texconv.py.
"""
import ctypes as c
import os


def mkdir(dir):
    """Make dir."""
    os.makedirs(dir, exist_ok=True)


HDR_FORMAT = [
    'BC6H_UF16',
    'R16G16B16A16_FLOAT'
]


class Texconv:
    """Texture converter."""
    def __init__(self, dll_path=None):
        """Constructor."""
        if dll_path is None:
            file_path = os.path.realpath(__file__)
            dll_path = os.path.join(os.path.dirname(file_path), "texconv.dll")
        if not os.path.exists(dll_path):
            so_path = dll_path[:-3] + "so"
            if not os.path.exists(so_path):
                print(f'texconv not found. ({dll_path})')
                self.dll = None
                return
            else:
                dll_path = so_path
        dll_path = os.path.abspath(dll_path)
        try:
            self.dll = c.cdll.LoadLibrary(dll_path)
        except Exception as e:
            print(f'Failed to load texconv. ({e})')
            self.dll = None

    def run(self, args):
        """Run texconv with args."""
        argc = len(args)
        args_p = [c.c_wchar_p(arg) for arg in args]
        args_p = (c.c_wchar_p*len(args_p))(*args_p)
        result = self.dll.texconv(argc, args_p, c.c_bool(False))
        if result != 0:
            raise RuntimeError('Failed to convert textures.')

    def convert(self, file, args, out=None):
        """Convert a texture with args."""
        if out is not None and isinstance(out, str):
            args += ['-o', out]
        else:
            out = '.'

        if out not in ['.', ''] and not os.path.exists(out):
            mkdir(out)

        args += ["-y"]
        args += [os.path.normpath(file)]
        self.run(args)
        return out

    def convert_to_tga(self, file, dds_fmt, texture_type='2D', out=None, invert_normals=False):
        """Convert dds to tga."""
        if self.dll is None:
            return None
        dds_fmt = FORMAT_FOR_TEXCONV[dds_fmt]
        if texture_type == 'Cube':
            raise RuntimeError('Can not convert cubemap textures with texconv.')
        fmt = 'tga'
        if dds_fmt in HDR_FORMAT:
            fmt = 'hdr'
        args = ['-ft', fmt]
        if 'BC5' in dds_fmt:
            args += ['-f', 'rgba', '-reconstructz']
            if invert_normals:
                args += ['-inverty']
        out = self.convert(file, args, out=out)
        name = os.path.join(out, os.path.basename(file))
        name = '.'.join(name.split('.')[:-1] + [fmt])
        return name

    def convert_to_dds(self, file, dds_fmt, texture_type='2D', out=None, invert_normals=False, no_mips=False):
        """Convert texture to dds."""
        dds_fmt = FORMAT_FOR_TEXCONV[dds_fmt]
        if texture_type == 'Cube':
            raise RuntimeError('Can not convert cubemap textures with texconv.')
        if dds_fmt in HDR_FORMAT and file[-3:].lower() != 'hdr':
            raise RuntimeError(f'Use .dds or .hdr to inject HDR textures. ({file})')
        args = ['-f', dds_fmt]
        if 'BC5' in dds_fmt and invert_normals:
            args += ['-inverty']
        if no_mips:
            args += ['-m', '1']
        self.convert(file, args, out=out)
        return file[:-3] + 'dds'


FORMAT_FOR_TEXCONV = {
    'DXT1/BC1': 'DXT1',
    'DXT5/BC3': 'DXT5',
    'BC4/ATI1': 'BC4_UNORM',
    'BC5/ATI2': 'BC5_UNORM',
    'BC6H(unsigned)': 'BC6H_UF16',
    'BC7': 'BC7_UNORM',
    'FloatRGBA': 'R16G16B16A16_FLOAT',
    'B8G8R8A8': 'B8G8R8A8_UNORM'
}
