#std
import os

#my libs
from ..util.io_util import *
from ..util.logger import logger
from ..util.cipher import Cipher
from .mesh import StaticMesh, SkeletalMesh
from .skeleton import SkeletonAsset
from .texture import Texture

class Uexp:

    UNREAL_SIGNATURE=b'\xC1\x83\x2A\x9E'
    
    def __init__(self, file, uasset):
        self.load(file, uasset)

    def load(self, file, uasset):
        if file[-4:]!='uexp':
            raise RuntimeError('Not .uexp! ({})'.format(file))
        if not os.path.exists(file):
            raise RuntimeError('FileNotFound: You should put .uexp in the same directory as .uasset. ({})'.format(file))

        #get name list and export data from .uasset
        self.uasset = uasset
        self.name_list=self.uasset.name_list        
        self.exports = self.uasset.exports
        self.imports = self.uasset.imports
        self.asset_path = self.uasset.asset_path

        self.version=self.uasset.version
        self.ff7r = self.version=='ff7r'
        self.asset_type = self.uasset.asset_type
        logger.log('FF7R: {}'.format(self.ff7r))
        logger.log('Asset type: {}'.format(self.asset_type))

        #check materials
        if self.asset_type in ['SkeletalMesh', 'StaticMesh']:
            has_material = False
            for imp in self.imports:
                if imp.material:
                    has_material=True
            if not has_material:
                raise RuntimeError('Material slot is empty. Be sure materials are assigned correctly in UE4.')

        #logger.log('Loading '+file+'...', ignore_verbose=True)
        #open .uexp
        self.mesh=None
        self.skeleton=None
        with open(file, 'rb') as f:
            for export in self.exports:
                if f.tell()+self.uasset.size!=export.offset:
                    raise RuntimeError('Parse failed.')

                if export.ignore:
                    logger.log('{} (offset: {})'.format(export.name, f.tell()))
                    logger.log('  size: {}'.format(export.size))
                    export.read_uexp(f)
                    
                else:
                    #'SkeletalMesh', 'StaticMesh', 'Skeleton'
                    if self.asset_type=='SkeletalMesh':
                        self.mesh=SkeletalMesh.read(f, self.ff7r, self.name_list, self.imports)
                        self.skeleton = self.mesh.skeleton
                    elif self.asset_type=='StaticMesh':
                        self.mesh=StaticMesh.read(f, self.ff7r, self.name_list, self.imports)
                    elif self.asset_type=='Skeleton':
                        self.skeleton = SkeletonAsset.read(f, self.name_list)
                    elif 'Texture' in self.asset_type:
                        self.texture = Texture.read(f, self.uasset)
                    self.unknown2=f.read(export.offset+export.size-f.tell()-self.uasset.size)

            #footer
            offset = f.tell()
            size = get_size(f)
            self.meta=f.read(size-offset-4)
            self.author = Cipher.decrypt(self.meta)                

            if self.author!='':
                print('Author: {}'.format(self.author))
            self.foot=f.read()
            check(self.foot, Uexp.UNREAL_SIGNATURE, f, 'Parse failed. (foot)')

    def load_material_asset(self):
        if self.mesh is not None:
            for m in self.mesh.materials:
                m.load_asset(self.uasset.actual_path, self.asset_path, version=self.version)

    def save(self, file):
        logger.log('Saving '+file+'...', ignore_verbose=True)
        with open(file, 'wb') as f:
            for export in self.exports:
                offset=f.tell()
                if export.ignore:
                    export.write_uexp(f)
                    size=export.size
                else:
                    if self.asset_type=='SkeletalMesh':
                        SkeletalMesh.write(f, self.mesh)
                    elif self.asset_type=='StaticMesh':
                        StaticMesh.write(f, self.mesh)
                    elif self.asset_type=='Skeleton':
                        SkeletonAsset.write(f, self.skeleton)
                    elif 'Texture' in self.asset_type:
                        self.texture.write(f)
                    else:
                        raise RuntimeError('Unsupported asset. ({})'.format(self.asset_type))
                    f.write(self.unknown2)
                    size=f.tell()-offset

                export.update(size, offset)

            f.write(self.meta)
            f.write(self.foot)
            uexp_size=f.tell()
        return uexp_size

    def remove_LODs(self):
        self.mesh.remove_LODs()

    def import_LODs(self, mesh_uexp, only_mesh=False, only_phy_bones=False,
                    dont_remove_KDI=False):
        if self.asset_type!=mesh_uexp.asset_type and self.asset_type!='Skeleton':
            raise RuntimeError('Asset types are not the same. ({}, {})'.format(self.asset_type, mesh_uexp.asset_type))
        if self.asset_type=='SkeletalMesh':
            self.mesh.import_LODs(mesh_uexp.mesh, self.imports, self.name_list, self.uasset.file_data_ids,
                                          only_mesh=only_mesh,
                                          only_phy_bones=only_phy_bones, dont_remove_KDI=dont_remove_KDI)
        elif self.asset_type=='StaticMesh':
            self.mesh.import_LODs(mesh_uexp.mesh, self.imports, self.name_list, self.uasset.file_data_ids)
        elif self.asset_type=='Skeleton':
            if mesh_uexp.asset_type=='SkeletalMesh':
                self.skeleton.import_bones(mesh_uexp.mesh.skeleton.bones, self.name_list, only_phy_bones=only_phy_bones)
            elif mesh_uexp.asset_type=='Skeleton':
                self.skeleton.import_bones(mesh_uexp.skeleton.bones, self.name_list, only_phy_bones=only_phy_bones)
            else:
                raise RuntimeError('ue4_18_file should have skeleton.')

    def import_from_blender(self, primitives, only_mesh=True):
        if self.skeleton is None and self.mesh is None:
            raise RuntimeError('Injection is not supported for {}'.format(self.asset_type))
        if self.mesh is None and only_mesh:
            raise RuntimeError("Enabled 'Only Mesh' option, but the asset have no meshes. ({})".format(self.asset_type))
        if not only_mesh and self.skeleton is not None:
            self.skeleton.import_bones(primitives['BONES'], self.name_list)
        if self.mesh is not None:
            self.mesh.import_from_blender(primitives, self.imports, self.name_list, self.uasset.file_data_ids, only_mesh=only_mesh)
        

    def remove_KDI(self):
        if self.asset_type=='SkeletalMesh':
            self.mesh.remove_KDI()
        else:
            raise RuntimeError('Unsupported feature for static mesh')

    def dump_buffers(self, save_folder):
        self.mesh.dump_buffers(save_folder)

    def embed_string(self, string):
        self.author=string
        self.meta=Cipher.encrypt(string)
        logger.log('A string has been embedded into uexp.', ignore_verbose=True)
        logger.log('  string: {}'.format(string))
        logger.log('  size: {}'.format(len(self.meta)), ignore_verbose=True)

    def get_author(self):
        return self.author

    def add_material_slot(self):
        if self.asset_type!='SkeletalMesh':
            raise RuntimeError('Unsupported feature for static mesh')
        self.mesh.add_material_slot(self.imports, self.name_list, self.uasset.file_data_ids)
        logger.log('Added a new material slot', ignore_verbose=True)

