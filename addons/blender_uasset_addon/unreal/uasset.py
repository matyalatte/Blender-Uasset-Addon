"""Classes for .uasset files."""
import ctypes as c
import os

from ..util import io_util as io
from ..util.crc import generate_hash
from ..util.version import VersionInfo
from .uexp import Uexp


class UassetHeader(c.LittleEndianStructure):
    """Class for uasset header."""
    HEAD = b'\xC1\x83\x2A\x9E'
    _pack_ = 1
    _fields_ = [  # 193 bytes
        # ("head", c.c_char*4), #Unreal Header (193,131,42,158)
        # ("version", c.c_int32), #-version-1=6 or 7
        # ("null", c.c_ubyte*16),
        ("uasset_size", c.c_uint32),  # size of .uasset
        ("str_length", c.c_uint32),  # 5
        ("none", c.c_char * 5),  # 'None '
        ("pkg_flags", c.c_uint32),  # 00 20 00 00: unversioned header flag
        ("name_count", c.c_uint32),
        ("name_offset", c.c_uint32),
        ("null2", c.c_ubyte * 8),
        ("export_count", c.c_uint32),
        ("export_offset", c.c_uint32),
        ("import_count", c.c_uint32),
        ("import_offset", c.c_uint32),
        ("end_to_export", c.c_uint32),
        ("null3", c.c_ubyte * 16),
        ("guid_hash", c.c_char * 16),
        ("unk2", c.c_uint32),
        ("padding_count", c.c_uint32),
        ("name_count2", c.c_uint32),  # name count again?
        ("null4", c.c_ubyte * 36),
        ("unk3", c.c_uint64),
        ("padding_offset", c.c_uint32),  # file data offset - 4
        ("file_length", c.c_uint32),  # .uasset + .uexp - 4
        ("null5", c.c_ubyte * 12),
        ("file_data_count", c.c_uint32),
        ("file_data_offset", c.c_uint32)
    ]

    def __init__(self):
        """Constructor."""
        super().__init__()
        self.version = 0
        self.null = b''
        self.unversioned = False
        self.unk_count = 0

    @staticmethod
    def read(f):
        """Read function."""
        header = UassetHeader()
        io.check(f.read(4), UassetHeader.HEAD)
        header.version = - io.read_int32(f) - 1
        if header.version not in [6, 7]:
            raise RuntimeError(f'Unsupported header version. ({header.version}')
        header.null = f.read(16 + 4 * (header.version >= 7))
        f.readinto(header)
        header.unversioned = (header.pkg_flags & 8192) != 0
        if header.version >= 7:
            header.unk_count = io.read_uint32(f)
            io.check(io.read_int32(f), -1)
            io.check(io.read_int32(f), -1)
        return header

    def write(self, f):
        """Write function."""
        f.write(UassetHeader.HEAD)
        io.write_int32(f, -self.version - 1)
        f.write(self.null)
        f.write(self)
        if self.version >= 7:
            io.write_uint32(f, self.unk_count)
            io.write_int32(f, -1)
            io.write_int32(f, -1)

    def print(self):
        """Print meta data."""
        print('Header info')
        print(f'  file size: {self.uasset_size}')
        print(f'  number of names: {self.name_count}')
        print('  name directory offset: 193')
        print(f'  number of exports: {self.export_count}')
        print(f'  export directory offset: {self.export_offset}')
        print(f'  number of imports: {self.import_count}')
        print(f'  import directory offset: {self.import_offset}')
        print(f'  end offset of export: {self.end_to_export}')
        print(f'  padding offset: {self.padding_offset}')
        print(f'  file length (uasset+uexp-4): {self.file_length}')
        print(f'  file data count: {self.file_data_count}')
        print(f'  file data offset: {self.file_data_offset}')


# import data of .uasset
class UassetImport(c.LittleEndianStructure):
    """Import data of .uasset."""
    _pack_ = 1
    _fields_ = [  # 28 bytes
        ("parent_dir_id", c.c_uint64),
        ("class_id", c.c_uint64),
        ("parent_import_id", c.c_int32),
        ("name_id", c.c_uint32),
        ("unk", c.c_uint32),
    ]

    def __init__(self):
        """Constructor."""
        super().__init__()
        self.material = False
        self.name = None
        self.class_name = None
        self.parent_dir = None
        self.unk2 = None

    @staticmethod
    def read(f, version):
        """Read function."""
        imp = UassetImport()
        f.readinto(imp)
        if version == '5.0':
            imp.unk2 = io.read_uint32(f)
        return imp

    def write(self, f, version):
        """Write function."""
        f.write(self)
        if version == '5.0':
            io.write_uint32(f, self.unk2)

    def name_import(self, name_list):
        """Convert ids to strings."""
        self.name = name_list[self.name_id]
        self.class_name = name_list[self.class_id]
        self.parent_dir = name_list[self.parent_dir_id]
        self.material = self.class_name in ['Material', 'MaterialInstanceConstant']
        return self.name

    def print(self, s='', padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + s + ': ' + self.name)
        print(pad + '  class: ' + self.class_name)
        print(pad + '  parent dir: ' + self.parent_dir)
        print(pad + '  parent import: ' + self.parent_name)

    def copy(self):
        """Copy itself."""
        copied = UassetImport()
        copied.parent_dir_id = self.parent_dir_id
        copied.class_id = self.class_id
        copied.parent_import_id = self.parent_import_id
        copied.name_id = self.name_id
        copied.unk = self.unk
        copied.material = self.material
        return copied


def name_imports(imports, name_list):
    """Convert ids to strings."""
    import_names = list(map(lambda x: x.name_import(name_list), imports))

    def name_parent(x):
        if x.parent_import_id == 0:
            x.parent_name = "None"
        else:
            x.parent_name = import_names[-x.parent_import_id - 1]

    list(map(name_parent, imports))


class UassetExport(c.LittleEndianStructure):
    """Export data of .uasset."""
    _pack_ = 1
    _fields_ = [  # 104 bytes
        ("class_id", c.c_int32),
        ("null", c.c_uint32),
        ("import_id", c.c_int32),
        ("null2", c.c_uint32),
        ("name_id", c.c_uint32),
        ("some", c.c_uint32),
        ("unk_int", c.c_uint32),
        ("size", c.c_uint64),
        ("offset", c.c_uint32),
        ("unk", c.c_ubyte * 64),
    ]

    MAIN_EXPORTS = ['SkeletalMesh', 'StaticMesh', 'Skeleton', 'AnimSequence',
                    'Texture2D', 'TextureCube', 'Material', 'MaterialInstanceConstant', 'BlendSpace']

    def __init__(self):
        """Constructor."""
        super().__init__()
        self.unk2 = None
        self.bin = None

    @staticmethod
    def read(f, version):
        """Read function."""
        exp = UassetExport()
        f.readinto(exp)
        if version == '5.0':
            exp.unk2 = io.read_uint32(f)
        return exp

    def write(self, f, version):
        """Write function."""
        f.write(self)
        if version == '5.0':
            io.write_uint32(f, self.unk2)

    def update(self, size, offset):
        """Update attributes."""
        self.size = size
        self.offset = offset

    @staticmethod
    def name_exports(exports, imports, name_list):
        """Convert ids to strings."""
        asset_type, asset_name = None, None
        for export in exports:
            export_import = imports[-export.import_id - 1]
            export.import_name = export_import.name
            export.name = name_list[export.name_id]
            export.class_name = export_import.class_name
            if export.class_name in UassetExport.MAIN_EXPORTS:
                asset_type = export.class_name
                asset_name = export.name
                export.ignore = False
            else:
                export.ignore = True
        return asset_type, asset_name

    def read_uexp(self, f):
        """Read .uexp and store export data as it is."""
        self.bin = f.read(self.size)

    def write_uexp(self, f):
        """Write export data as it is."""
        f.write(self.bin)

    def print(self, padding=2):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + self.name)
        print(pad + f'  class: {self.class_name}')
        print(pad + f'  import: {self.import_name}')
        print(pad + f'  size: {self.size}')
        print(pad + f'  offset: {self.offset}')


class Uasset:
    """Class for .uasset file."""

    def __init__(self, file, version='ff7r', ignore_uexp=False, asset_type='', verbose=False):
        """Load an asset file."""
        ext = io.get_ext(file)
        base = file[:-len(ext)]
        if ext != 'uasset':
            if ext != 'uexp':
                raise RuntimeError(f'Not .uasset! ({file})')
            file = base + 'uasset'

        print('Loading ' + file + '...')

        self.actual_path = file
        self.file = os.path.basename(file)[:-7]
        self.name = os.path.splitext(os.path.basename(file))[0]
        if version == 'ff7r':
            base_version = '4.18'
            custom_version = version
        elif version == 'kh3':
            base_version = '4.17'
            custom_version = version
        else:
            base_version = version
            custom_version = None
        self.version = VersionInfo(base_version, customized_version=custom_version)

        with open(file, 'rb') as f:
            self.size = io.get_size(f)
            # read header
            self.header = UassetHeader.read(f)
            self.unversioned = self.header.unversioned

            if verbose:
                print(f'size: {self.size}')
                self.header.print()
                print('Name list')

            # read name table
            def read_names(f, i):
                name = io.read_str(f)
                hash_ = f.read(4)
                if verbose:
                    print(f'  {i}: {name}')
                return name, hash_
            names = [read_names(f, i) for i in range(self.header.name_count)]
            self.name_list = [x[0] for x in names]
            self.hash_list = [x[1] for x in names]

            # read imports
            io.check(self.header.import_offset, f.tell(), f)
            self.imports = [UassetImport.read(f, self.version) for i in range(self.header.import_count)]
            name_imports(self.imports, self.name_list)
            if verbose:
                print('Import')
                list(map(lambda x, i: x.print(str(i)), self.imports, range(len(self.imports))))

            # read exports
            io.check(self.header.export_offset, f.tell(), f)
            self.exports = [UassetExport.read(f, self.version) for i in range(self.header.export_count)]
            self.asset_type, self.asset_name = UassetExport.name_exports(self.exports, self.imports, self.name_list)

            if verbose:
                print('Export')
                list(map(lambda x: x.print(), self.exports))

            if self.asset_type is None:
                raise RuntimeError(f'Unsupported asset ({self.asset_type})')
            if asset_type not in self.asset_type:
                raise RuntimeError(f'Not {asset_type}. ({self.asset_type})')

            import_names = [imp.name for imp in self.imports]
            paths = [n for n in self.name_list if n[0] == '/' and n not in import_names]
            paths = [p for p in paths if p.split('/')[-1] in self.asset_name]
            if len(paths) != 1:
                paths = [p for p in paths if self.asset_name in p.split('/')[-1]]
                if len(paths) != 1:
                    raise RuntimeError('Failed to get asset path.')
            self.asset_path = paths[0]

            io.check(self.header.end_to_export, f.tell())

            io.read_null_array(f, self.header.padding_count)
            io.check(self.header.padding_offset, f.tell())
            io.read_null(f)
            io.check(self.header.file_data_offset, f.tell())
            self.file_data_ids = io.read_int32_array(f, length=self.header.file_data_count)

            io.check(f.tell(), self.size)
            io.check(self.header.uasset_size, self.size)

        if ignore_uexp:
            return

        self.uexp = Uexp(base + 'uexp', self, verbose=verbose)

    def save(self, file):
        """Save an asset file."""
        ext = io.get_ext(file)
        base = file[:-len(ext)]
        if ext != 'uasset':
            if ext != 'uexp':
                raise RuntimeError(f'Not .uasset! ({file})')
            file = base + 'uasset'

        directory = os.path.dirname(file)
        if directory != '' and not os.path.exists(directory):
            io.mkdir(directory)

        uexp_file = base + 'uexp'
        uexp_size = self.uexp.save(uexp_file)

        print('Saving ' + file + '...')
        with open(file, 'wb') as f:
            # skip header part
            f.seek(self.header.name_offset)

            # self.header.name_offset = f.tell()
            self.header.name_count = len(self.name_list)
            self.header.name_count2 = len(self.name_list)
            # write name table
            self.hash_list = [generate_hash(name) for name in self.name_list]
            for name, hash_ in zip(self.name_list, self.hash_list):
                io.write_str(f, name)
                f.write(hash_)

            # write imports
            self.header.import_offset = f.tell()
            self.header.import_count = len(self.imports)
            list(map(lambda x: x.write(f, self.version), self.imports))

            # skip exports part
            self.header.export_offset = f.tell()
            self.header.export_count = len(self.exports)
            list(map(lambda x: x.write(f, self.version), self.exports))
            self.header.end_to_export = f.tell()

            # file data ids
            io.write_null_array(f, self.header.padding_count + 1)
            self.header.padding_offset = f.tell() - 4
            self.header.file_data_offset = f.tell()
            self.header.file_data_count = len(self.file_data_ids)
            io.write_int32_array(f, self.file_data_ids)
            self.header.uasset_size = f.tell()
            self.header.file_length = uexp_size + self.header.uasset_size - 4

            # write header
            f.seek(0)
            self.header.write(f)

            # write exports
            f.seek(self.header.export_offset)
            offset = self.header.uasset_size
            for export in self.exports:
                export.update(export.size, offset)
                offset += export.size
            list(map(lambda x: x.write(f, self.version), self.exports))
