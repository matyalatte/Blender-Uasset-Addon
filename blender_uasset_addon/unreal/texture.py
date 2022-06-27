import os
from ..util.io_util import *
from .mipmap import Mipmap

#classes for texture assets (.uexp and .ubulk)

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
    'B8G8R8A8(sRGB)': 4
}

PF_FORMAT = {
    'PF_DXT1': 'DXT1/BC1',
    'PF_DXT5': 'DXT5/BC3',
    'PF_BC4': 'BC4/ATI1',
    'PF_BC5': 'BC5/ATI2',
    'PF_BC6H': 'BC6H(unsigned)',
    'PF_BC7': 'BC7', 
    'PF_FloatRGBA': 'FloatRGBA',
    'PF_B8G8R8A8': 'B8G8R8A8(sRGB)'
}

def is_power_of_2(n):
    if n==1:
        return True
    if n%2!=0:
        return False
    return is_power_of_2(n//2)

#get all file paths for texture asset from a file path.
EXT = ['.uasset', '.uexp', '.ubulk']
def get_all_file_path(file):
    base_name, ext = os.path.splitext(file)
    if ext not in EXT:
        raise RuntimeError('Not Uasset. ({})'.format(file))
    return [base_name + ext for ext in EXT]

VERSION_ERR_MSG = 'Make sure you specified UE4 version correctly.'

#texture class for ue4
class Texture:
    UNREAL_SIGNATURE = b'\xC1\x83\x2A\x9E'
    UBULK_FLAG = [0, 16384]
    
    def read(f, uasset, verbose=False):
        return Texture(f, uasset, verbose=verbose)

    def __init__(self, f, uasset, verbose=False):
        self.uasset = uasset
        version = self.uasset.version
        if version=='4.26':
            version='4.27'
        if version in ['4.23', '4.24']:
            version='4.25'
        if version in ['4.21', '4.22']:
            version='4.20'

        file_path = f.name
        
        uasset_name, uexp_name, ubulk_name = get_all_file_path(file_path)

        self.version = version

        if len(self.uasset.exports)!=1:
            raise RuntimeError('Unexpected number of exports')

        self.uasset_size = self.uasset.size
        self.name_list = self.uasset.name_list
        self.texture_type = '2D' if self.uasset.asset_type=='Texture2D' else 'Cube'
        
        #read .uexp
        self.read_uexp(f)
        
        #read .ubulk
        if self.has_ubulk:
            with open(ubulk_name, 'rb') as bulk_f:
                size = get_size(bulk_f)
                for mip in self.mipmaps:
                    if mip.uexp:
                        continue
                    mip.data = bulk_f.read(mip.data_size)
                check(size, bulk_f.tell())

        if verbose:
            self.print()
    
    #read uexp
    def read_uexp(self, f):
        #read cooked size if exist
        self.bin1=None
        self.imported_width=None
        self.imported_height=None
        if self.version=='ff7r':
        #if self.unversioned:
            uh = read_uint8_array(f, 2)
            is_last=uh[1]%2==0
            while (is_last):
                uh = read_uint8_array(f, 2)
                is_last=uh[1]%2==0
                if f.tell()>100:
                    raise RuntimeError('Parse Failed. ' + VERSION_ERR_MSG)
            s = f.tell()
            f.seek(0)
            self.bin1=f.read(s)
            chk = read_uint8_array(f, 8)
            chk = [i for i in chk if i==0]
            f.seek(-8, 1)            
            if len(chk)>2:
                self.imported_width = read_uint32(f)
                self.imported_height = read_uint32(f)
        else:
            first_property_id = read_uint64(f)
            if first_property_id>=len(self.name_list):
                raise RuntimeError('list index out of range. ' + VERSION_ERR_MSG)
            first_property = self.name_list[first_property_id]
            f.seek(0)
            if first_property=='ImportedSize':
                self.bin1 = f.read(49)
                self.imported_width = read_uint32(f)
                self.imported_height = read_uint32(f)

        #skip property part        
        offset=f.tell()
        b = f.read(8)
        while (b!=b'\x01\x00\x01\x00\x01\x00\x00\x00'):
            b=b''.join([b[1:], f.read(1)])
            if f.tell()>1000:
                    raise RuntimeError('Parse Failed. ' + VERSION_ERR_MSG)
        s=f.tell()-offset
        f.seek(offset)        
        self.unk = f.read(s)

        #read meta data
        self.type_name_id = read_uint64(f)
        self.offset_to_end_offset = f.tell()
        self.end_offset = read_uint32(f) #Offset to end of uexp?
        if self.version in ['4.25', '4.27', '4.20']:
            read_null(f, msg='Not NULL! ' + VERSION_ERR_MSG)
        self.original_width = read_uint32(f)
        self.original_height = read_uint32(f)
        self.cube_flag = read_uint16(f)
        self.unk_int = read_uint16(f)
        if self.cube_flag==1:
            if self.texture_type!='2D':
                raise RuntimeError('Unexpected error! Please report it to the developer.')
        elif self.cube_flag==6:
            if self.texture_type!='Cube':
                raise RuntimeError('Unexpected error! Please report it to the developer.')
        else:
            raise RuntimeError('Not a cube flag! ' + VERSION_ERR_MSG)
        self.type = read_str(f)
        if self.version=='ff7r' and self.unk_int==Texture.UBULK_FLAG[1]:
            read_null(f)
            read_null(f)
            ubulk_map_num = read_uint32(f) #bulk map num + unk_map_num
        self.unk_map_num=read_uint32(f) #number of some mipmaps in uexp
        map_num = read_uint32(f) #map num ?

        if self.version=='ff7r':
            #ff7r has all mipmap data in a mipmap object
            self.uexp_mip_bulk = Mipmap.read(f, 'ff7r')
            read_const_uint32(f, self.cube_flag)
            f.seek(4, 1) #uexp mip map num

        #read mipmaps
        self.mipmaps = [Mipmap.read(f, self.version) for i in range(map_num)]
        _, ubulk_map_num = self.get_mipmap_num()
        self.has_ubulk=ubulk_map_num>0

        #get format name
        if self.type not in PF_FORMAT:
            raise RuntimeError('Unsupported format. ({})'.format(self.type))
        self.format_name = PF_FORMAT[self.type]
        self.byte_per_pixel = BYTE_PER_PIXEL[self.format_name]

        if self.version=='ff7r':
            #split mipmap data
            i=0
            for mip in self.mipmaps:
                if mip.uexp:
                    size = int(mip.pixel_num*self.byte_per_pixel*self.cube_flag)
                    mip.data = self.uexp_mip_bulk.data[i:i+size]
                    i+=size
            check(i, len(self.uexp_mip_bulk.data))

        if self.version in ['4.25', '4.27']:
            read_null(f, msg='Not NULL! ' + VERSION_ERR_MSG)
        #check(self.end_offset, f.tell()+self.uasset_size)
        self.none_name_id = read_uint64(f)

    #get max size of uexp mips
    def get_max_uexp_size(self):
        for mip in self.mipmaps:
            if mip.uexp:
                break
        return mip.width, mip.height

    #get max size of mips
    def get_max_size(self):
        return self.mipmaps[0].width, self.mipmaps[0].height

    #get number of mipmaps
    def get_mipmap_num(self):
        uexp_map_num = 0
        ubulk_map_num = 0
        for mip in self.mipmaps:
            uexp_map_num+=mip.uexp
            ubulk_map_num+=not mip.uexp
        return uexp_map_num, ubulk_map_num

    #save as uasset
    def write(self, f):
        file_path = f.name
        folder = os.path.dirname(file_path)
        if folder not in ['.', ''] and not os.path.exists(folder):
            mkdir(folder)

        uasset_name, uexp_name, ubulk_name = get_all_file_path(file_path)
        if not self.has_ubulk:
            ubulk_name = None
        
        #write .uexp
        self.write_uexp(f)

        #write .ubulk if exist
        if self.has_ubulk:
            with open(ubulk_name, 'wb') as bulk_f:
                for mip in self.mipmaps:
                    if not mip.uexp:
                        bulk_f.write(mip.data)

    def write_uexp(self, f, valid=False):
        #get mipmap info
        max_width, max_height = self.get_max_size()
        uexp_map_num, ubulk_map_num = self.get_mipmap_num()
        uexp_map_data_size = 0
        for mip in self.mipmaps:
            if mip.uexp:
                uexp_map_data_size += len(mip.data)+32*(self.version!='ff7r')
        
        #write cooked size if exist
        if self.bin1 is not None:
            f.write(self.bin1)

        if self.imported_height is not None:
            if not valid:
                self.imported_height=max(self.original_height, max_height)
                self.imported_width=max(self.original_width, max_width)
            write_uint32(f, self.imported_width)
            write_uint32(f, self.imported_height)

        if not valid:
            self.original_height=max_height
            self.original_width =max_width

        f.write(self.unk)

        #write meta data
        write_uint64(f, self.type_name_id)
        write_uint32(f, 0) #write dummy offset. (rewrite it later)
        if self.version in ['4.25', '4.27', '4.20']:
            write_null(f)
        
        write_uint32(f, self.original_width)
        write_uint32(f, self.original_height)
        write_uint16(f, self.cube_flag)
        write_uint16(f, self.unk_int)

        write_str(f, self.type)

        if self.version=='ff7r' and self.unk_int==Texture.UBULK_FLAG[1]:
            write_null(f)
            write_null(f)
            write_uint32(f, ubulk_map_num+self.unk_map_num)
        
        write_uint32(f, self.unk_map_num)
        write_uint32(f, len(self.mipmaps))

        if self.version=='ff7r':
            #pack mipmaps in a mipmap object
            uexp_bulk=b''
            for mip in self.mipmaps:
                mip.meta=True
                if mip.uexp:
                    uexp_bulk = b''.join([uexp_bulk, mip.data])
            size = self.get_max_uexp_size()
            self.uexp_mip_bulk=Mipmap('ff7r')
            self.uexp_mip_bulk.update(uexp_bulk, size, True)
            self.uexp_mip_bulk.offset=self.uasset_size+f.tell()+24
            self.uexp_mip_bulk.write(f)

            write_uint32(f, self.cube_flag)
            write_uint32(f, uexp_map_num)
        
        #write mipmaps
        ubulk_offset = 0
        for mip in self.mipmaps:
            if mip.uexp:
                mip.offset=self.uasset_size+f.tell()+24
            else:
                mip.offset=ubulk_offset
                ubulk_offset+=mip.data_size
            mip.write(f)

        if self.version in ['4.25', '4.27']:
            write_null(f)
        new_end_offset = f.tell() + self.uasset_size
        write_uint64(f, self.none_name_id)

        if self.version not in ['4.27', 'ff7r']:
            base_offset = - self.uasset_size - f.tell()
            for mip in self.mipmaps:
                if not mip.uexp:
                    mip.offset += base_offset
                    mip.rewrite_offset(f)
        
        f.seek(self.offset_to_end_offset)
        write_uint32(f, new_end_offset)
        f.seek(0, 2)

    #remove mipmaps except the largest one
    def remove_mipmaps(self):
        old_mipmap_num = len(self.mipmaps)
        if old_mipmap_num==1:
            return
        self.mipmaps = [self.mipmaps[0]]
        self.mipmaps[0].uexp=True
        self.has_ubulk=False
        #print('mipmaps have been removed.')
        #print('  mipmap: {} -> 1'.format(old_mipmap_num))

    #inject dds into asset
    def inject_dds(self, dds, force=False):
        #check formats
        if '(signed)' in dds.header.format_name:
            raise RuntimeError('UE4 requires unsigned format but your dds is {}.'.format(dds.header.format_name))

        if dds.header.format_name!=self.format_name and not force:
            raise RuntimeError('The format does not match. ({}, {})'.format(self.type, dds.header.format_name))

        if dds.header.texture_type!=self.texture_type:
            raise RuntimeError('Texture type does not match. ({}, {})'.format(self.texture_type, dds.header.texture_type))
        
        '''
        def get_key_from_value(d, val):
            keys = [k for k, v in d.items() if v == val]
            if keys:
                return keys[0]
            return None

        if force:
            self.format_name = dds.header.format_name
            new_type = get_key_from_value(self.format_name)
            self.uasset_size+=len(new_type)-len(self.type)
            self.type = new_type
            self.name_list[self.type_name_id]=self.type
            self.byte_per_pixel = BYTE_PER_PIXEL[self.format_name]
        '''
            
        max_width, max_height = self.get_max_size()
        old_size = (max_width, max_height)
        old_mipmap_num = len(self.mipmaps)

        uexp_width, uexp_height = self.get_max_uexp_size()

        #inject
        i=0
        self.mipmaps=[Mipmap(self.version) for i in range(len(dds.mipmap_data))]
        for data, size, mip in zip(dds.mipmap_data, dds.mipmap_size, self.mipmaps):
            if self.has_ubulk and i+1<len(dds.mipmap_data) and size[0]*size[1]>uexp_width*uexp_height:
                mip.update(data, size, False)
            else:
                mip.update(data, size, True)
            i+=1

        #print results
        max_width, max_height = self.get_max_size()
        new_size = (max_width, max_height)
        _, ubulk_map_num = self.get_mipmap_num()
        if ubulk_map_num==0:
            self.has_ubulk=False
        if self.version=="ff7r":
            self.unk_int=Texture.UBULK_FLAG[self.has_ubulk]
        new_mipmap_num = len(self.mipmaps)

        print('dds has been injected.')
        print('  size: {} -> {}'.format(old_size, new_size))
        print('  mipmap: {} -> {}'.format(old_mipmap_num, new_mipmap_num))
        
        #warnings
        if new_mipmap_num>1 and (not is_power_of_2(max_width) or not is_power_of_2(max_height)):
            print('Warning: Mipmaps should have power of 2 as its width and height. ({}, {})'.format(max_width, max_height))
        if new_mipmap_num>1 and old_mipmap_num==1:
            print('Warning: The original texture has only 1 mipmap. But your dds has multiple mipmaps.')
            

    def print(self):
        for mip, i in zip(self.mipmaps, range(len(self.mipmaps))):
            print('Mipmap{}'.format(i))
            mip.print()
        return
