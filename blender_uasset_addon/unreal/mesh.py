import os, json, struct
from ..util.io_util import *

from .lod import StaticLOD, SkeletalLOD4, SkeletalLOD5
from .skeleton import Skeleton
from .material import Material, StaticMaterial, SkeletalMaterial
from .buffer import Buffer

#Base class for mesh
class Mesh:
    def __init__(self, LODs):
        self.LODs = LODs

    def remove_LODs(self):
        num=len(self.LODs)
        if num<=1:
            return

        self.LODs=[self.LODs[0]]

        print('Removed LOD1~{}'.format(num-1))

    def dump_buffers(self, save_folder):
        logs={}
        for lod,i in zip(self.LODs, range(len(self.LODs))):
            log={}
            for buf in lod.get_buffers():
                file_name='LOD{}_{}'.format(i, buf.name)+'.buf'
                file=os.path.join(save_folder, file_name)
                Buffer.dump(file, buf)
                offset, stride, size = buf.get_meta()
                log[buf.name]={'offset': offset, 'stride': stride, 'size': size}

            logs['LOD{}'.format(i)]=log
        
        file=os.path.join(save_folder,'log.json'.format(i))
        with open(file, 'w') as f:
            json.dump(logs, f, indent=4)

    def seek_materials(f, imports, seek_import=False):
        offset=f.tell()
        buf=f.read(3)
        size = get_size(f)
        while (True):
            while (buf!=b'\xff'*3):
                if b'\xff' not in buf:
                    buf = f.read(3)
                else:
                    buf=b''.join([buf[1:], f.read(1)])
                if f.tell()==size:
                    raise RuntimeError('Material properties not found. This is an unexpected error.')
            f.seek(-4,1)
            import_id=-read_int32(f)-1
            if imports[import_id].material or seek_import:
                break
            #print(imports[import_id].name)
            buf=f.read(3)
        return

    def add_material_slot(self, imports, name_list, file_data_ids, material):
        if type(material)==type(""):
            slot_name = material
            import_name = material
            file_path = '/Game/GameContents/path_to_'+material
        else:
            slot_name = material.slot_name
            import_name = material.import_name
            file_path = material.file_path

        #add material slot
        import_id = self.materials[-1].import_id
        new_material = self.materials[-1].copy()
        new_material.import_id = -len(imports)-1
        new_material.slot_name_id = len(name_list)
        self.materials.append(new_material)
        name_list.append(slot_name)
        file_data_ids.append(-len(imports)-1)

        #add import for material
        sample_material_import = imports[-import_id-1]
        new_material_import = sample_material_import.copy()
        imports.append(new_material_import)
        new_material_import.parent_import_id = -len(imports)-1
        new_material_import.name_id = len(name_list)
        name_list.append(import_name)

        #add import for material dir
        sample_dir_import = imports[-sample_material_import.parent_import_id-1]
        new_dir_import = sample_dir_import.copy()
        imports.append(new_dir_import)
        new_dir_import.name_id = len(name_list)
        name_list.append(file_path)

    def import_from_blender(self, primitives, imports, name_list, file_data_ids, only_mesh = True):
        materials = primitives['MATERIALS']
        if len(self.materials)<len(materials):
            raise RuntimeError('Can not add material slots. (source file: {}, blender: {})'.format(len(self.materials), len(materials)))
            ignore_material_names=True
            added_num = len(materials)-len(self.materials)
            for i in range(added_num):
                self.add_material_slot(imports, name_list, file_data_ids, materials[len(self.materials)].name)
            logger.warn('Added {} materials. You need to edit name table to use the new materials.'.format(added_num))

        new_material_ids = Material.assign_materials(self.materials, materials)
        
        self.remove_LODs()
        lod = self.LODs[0]
        lod.import_from_blender(primitives)
        lod.update_material_ids(new_material_ids)

#static mesh
class StaticMesh(Mesh):
    def __init__(self, unk, materials, LODs):
        self.unk = unk
        self.materials = materials
        self.LODs = LODs
        
    def read(f, uasset, verbose=False):
        imports = uasset.imports
        name_list = uasset.name_list
        version = uasset.version
        offset=f.tell()
        Mesh.seek_materials(f, imports)
        f.seek(-10-(51+21)*(version!='ff7r'),1)
        material_offset=f.tell()
        num = read_uint32(f)
        f.seek((version!='ff7r')*(51+21), 1)

        materials=[]
        for i in range(num):
            if i>0:
                Mesh.seek_materials(f, imports)
                f.seek(-6, 1)
            materials.append(StaticMaterial.read(f))
        
        Material.update_material_data(materials, name_list, imports)
        if verbose:
            print('Materials (offset: {})'.format(material_offset))
            for material in materials:
                material.print()
        
        buf=f.read(6)
        while (buf!=b'\x01\x00\x01\x00\x00\x00'):
            buf=b''.join([buf[1:], f.read(1)])
        unk_size=f.tell()-offset+28

        f.seek(offset)
        unk = f.read(unk_size)
        LODs = read_array(f, StaticLOD.read)
        if verbose:
            for i in range(len(LODs)):
                LODs[i].print(i)
        return StaticMesh(unk, materials, LODs)

    def write(f, staticmesh):
        f.write(staticmesh.unk)
        write_array(f, staticmesh.LODs, StaticLOD.write, with_length=True)
    
    def import_LODs(self, mesh, imports, name_list, file_data_ids):
        if len(self.materials)<len(mesh.materials):
            raise RuntimeError('Can not add materials to static mesh.')
        ignore_material_names=False
        super().import_LODs(mesh, imports, name_list, file_data_ids, ignore_material_names=ignore_material_names)

#skeletal mesh
class SkeletalMesh(Mesh):
    #unk: ?
    #materials: material names
    #skeleton: skeleton data
    #LOD: LOD array
    #extra_mesh: ?
    def __init__(self, version, unk, materials, skeleton, LODs, extra_mesh):
        self.version=version
        self.unk=unk
        self.materials=materials
        self.skeleton=skeleton
        self.LODs=LODs
        self.extra_mesh=extra_mesh
        
    def read(f, uasset, verbose=False):
        imports = uasset.imports
        name_list = uasset.name_list
        version = uasset.version
        offset=f.tell()

        Mesh.seek_materials(f, imports)
        f.seek(-8,1)
        unk_size=f.tell()-offset
        f.seek(offset)
        unk=f.read(unk_size)

        material_offset=f.tell()
        materials=[SkeletalMaterial.read(f, version) for i in range(read_uint32(f))]
        Material.update_material_data(materials, name_list, imports)
        if verbose:
            print('Materials (offset: {})'.format(material_offset))
            for material in materials:
                material.print()

        #skeleton data
        skeleton=Skeleton.read(f, version)
        skeleton.name_bones(name_list)
        if verbose:
            skeleton.print()

        if version>='4.27':
            read_const_uint32(f, 1)

        #LOD data
        if version<'4.27':
            LODs=[SkeletalLOD4.read(f, version) for i in range(read_uint32(f))]
        else:
            LODs=[SkeletalLOD5.read(f, version) for i in range(read_uint32(f))]
        if verbose:
            for lod, i in zip(LODs,range(len(LODs))):
                lod.print(str(i), skeleton.bones)

        #mesh data?
        if version=='ff7r':
            read_const_uint32(f, 1)
            extra_mesh=ExtraMesh.read(f, skeleton.bones)
            if verbose:
                extra_mesh.print()
        else:
            extra_mesh=None
        return SkeletalMesh(version, unk, materials, skeleton, LODs, extra_mesh)

    def write(f, skeletalmesh):
        f.write(skeletalmesh.unk)
        write_array(f, skeletalmesh.materials, SkeletalMaterial.write, with_length=True)
        Skeleton.write(f, skeletalmesh.skeleton)
        if skeletalmesh.version>='4.27':
            write_uint32(f, 1)
        if skeletalmesh.version<'4.27':
            write_array(f, skeletalmesh.LODs, SkeletalLOD4.write, with_length=True)
        else:
            write_array(f, skeletalmesh.LODs, SkeletalLOD5.write, with_length=True)
        if skeletalmesh.version=='ff7r':
            write_uint32(f, 1)
            ExtraMesh.write(f, skeletalmesh.extra_mesh)

    def import_LODs(self, skeletalmesh, imports, name_list, file_data_ids, only_mesh=False, only_phy_bones=False,
                    dont_remove_KDI=False):
        if self.version!='ff7r':
            raise RuntimeError("The file should be an FF7R's asset!")

        bone_diff=len(self.skeleton.bones)-len(skeletalmesh.skeleton.bones)
        if (only_mesh or only_phy_bones) and bone_diff!=0:
            msg = 'Skeletons are not the same.'
            if bone_diff==-1:
                msg+=' Maybe UE4 added an extra bone as a root bone.'
            raise RuntimeError(msg)

        if not only_mesh:
            self.skeleton.import_bones(skeletalmesh.skeleton.bones, name_list, only_phy_bones=only_phy_bones)
            #print(len(name_list))
            if self.extra_mesh is not None:
                self.extra_mesh.update_bone_ids(self.skeleton.bones)

        ignore_material_names=False
        if len(self.materials)<len(skeletalmesh.materials):
            ignore_material_names=True
            added_num = len(skeletalmesh.materials)-len(self.materials)
            for i in range(added_num):
                self.add_material_slot(imports, name_list, file_data_ids, skeletalmesh.materials[len(self.materials)])

        super().import_LODs(skeletalmesh, imports, name_list, file_data_ids, ignore_material_names=ignore_material_names)

        if not dont_remove_KDI:
            self.remove_KDI()

    def remove_KDI(self):
        if self.version!='ff7r':
            raise RuntimeError("The file should be an FF7R's asset!")
        
        for lod in self.LODs:
            lod.remove_KDI()

        print("KDI buffers have been removed.")

    def import_from_blender(self, primitives, imports, name_list, file_data_ids, only_mesh = True):
        bones = primitives['BONES']
        if only_mesh:
            if len(bones)!=len(self.skeleton.bones):
                raise RuntimeError('The number of bones are not the same. (source file: {}, blender: {})'.format(len(self.skeleton.bones), len(bones)))

        if self.extra_mesh is not None and not only_mesh:
            self.extra_mesh.disable()
        super().import_from_blender(primitives, imports, name_list, file_data_ids)

#Skeletal meshes have an extra low poly mesh.
#I removed buffers from this mesh, but it won't affect physics
#(collision with other objects, and collision between body and cloth)
class ExtraMesh:
    def __init__(self, f, bones):
        self.offset=f.tell()
        self.names = [b.name for b in bones]
        vertex_num=read_uint32(f)
        self.vb=f.read(vertex_num*12)
        read_const_uint32(f, vertex_num)
        self.weight_buffer=list(struct.unpack('<'+'HHHHBBBB'*vertex_num, f.read(vertex_num*12)))
        face_num=read_uint32(f)
        self.ib=f.read(face_num*6)
        self.unk = f.read(8)

    def disable(self):
        self.vb=b''
        self.weight_buffer=b''
        self.ib=b''

    def read(f, bones):
        return ExtraMesh(f, bones)

    def write(f, mesh):
        vertex_num = len(mesh.vb)//12
        write_uint32(f, vertex_num)
        f.write(mesh.vb)
        write_uint32(f, vertex_num)
        f.write(struct.pack('<'+'HHHHBBBB'*vertex_num, *mesh.weight_buffer))

        #f.write(mesh.weight_buffer)
        write_uint32(f, len(mesh.ib)//6)
        f.write(mesh.ib)
        f.write(mesh.unk)

    def print(self, padding=0):
        pad=' '*padding
        print(pad+'Mesh (offset: {})'.format(self.offset))
        print(pad+'  vertex_num: {}'.format(len(self.vb)//12))
        print(pad+'  face_num: {}'.format(len(self.ib)//6))
