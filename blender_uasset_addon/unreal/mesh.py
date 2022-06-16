import os, json, struct
from ..util.io_util import *
from ..util.logger import logger

from .lod import StaticLOD, SkeletalLOD
from .skeleton import Skeleton, Bone
from .material import Material, StaticMaterial, SkeletalMaterial
from .buffer import Buffer

#Base class for mesh
class Mesh:
    def __init__(self, LODs):
        self.LODs = LODs

    def remove_LODs(self):
        num=len(self.LODs)
        if num<=1:
            logger.log('Nothing has been removed.'.format(num-1), ignore_verbose=True)
            return

        self.LODs=[self.LODs[0]]

        logger.log('LOD1~{} have been removed.'.format(num-1), ignore_verbose=True)

    def import_LODs(self, mesh, imports, name_list, file_data_ids, ignore_material_names=False):

        new_material_ids = Material.check_confliction(self.materials, mesh.materials, ignore_material_names=ignore_material_names)
        
        LOD_num_self=len(self.LODs)
        LOD_num=min(LOD_num_self, len(mesh.LODs))
        #LOD_num=1
        if LOD_num<LOD_num_self:
            self.LODs=self.LODs[:LOD_num]
            logger.log('LOD{}~{} have been removed.'.format(LOD_num, LOD_num_self-1), ignore_verbose=True)
        for i in range(LOD_num):
            new_lod = mesh.LODs[i]
            new_lod.update_material_ids(new_material_ids)
            self.LODs[i].import_LOD(new_lod, str(i))

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
        while (True):
            while (buf!=b'\xFF\xFF\xFF'):
                buf=b''.join([buf[1:], f.read(1)])
                if f.tell()-offset>100000:
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

#static mesh
class StaticMesh(Mesh):
    def __init__(self, unk, materials, LODs):
        self.unk = unk
        self.materials = materials
        self.LODs = LODs
        
    def read(f, ff7r, name_list, imports):
        offset=f.tell()
        Mesh.seek_materials(f, imports)
        f.seek(-10-(51+21)*(not ff7r),1)
        material_offset=f.tell()
        num = read_uint32(f)
        f.seek((not ff7r)*(51+21), 1)

        materials=[]
        for i in range(num):
            if i>0:
                Mesh.seek_materials(f, imports)
                f.seek(-6, 1)
            materials.append(StaticMaterial.read(f))
            
        Material.print_materials(materials, name_list, imports, material_offset)
        
        buf=f.read(6)
        while (buf!=b'\x01\x00\x01\x00\x00\x00'):
            buf=b''.join([buf[1:], f.read(1)])
        unk_size=f.tell()-offset+28

        f.seek(offset)
        unk = f.read(unk_size)
        LODs = read_array(f, StaticLOD.read)
        for i in range(len(LODs)):
            LODs[i].print(i)
        return StaticMesh(unk, materials, LODs)

    def write(f, staticmesh):
        f.write(staticmesh.unk)
        write_array(f, staticmesh.LODs, StaticLOD.write, with_length=True)
    
    def save_as_gltf(self, name, save_folder):
        material_names = [m.import_name for m in self.materials]
        material_ids, uv_num = self.LODs[0].get_meta_for_gltf()
        #gltf = glTF(None, material_names, material_ids, uv_num)
        normals, tangents, positions, texcoords, indices= self.LODs[0].parse_buffers_for_gltf()
        #gltf.set_parsed_buffers(normals, tangents, positions, texcoords, None, None, None, None, indices)
        #gltf.save(name, save_folder)

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
    #phy_mesh: ?
    def __init__(self, ff7r, unk, materials, skeleton, LODs, phy_mesh):
        self.ff7r=ff7r
        self.unk=unk
        self.materials=materials
        self.skeleton=skeleton
        self.LODs=LODs
        self.phy_mesh=phy_mesh
        
    def read(f, ff7r, name_list, imports):
        offset=f.tell()

        Mesh.seek_materials(f, imports)
        f.seek(-8,1)
        unk_size=f.tell()-offset
        f.seek(offset)
        unk=f.read(unk_size)

        material_offset=f.tell()
        materials=read_array(f, SkeletalMaterial.read)
        Material.print_materials(materials, name_list, imports, material_offset)

        #skeleton data
        skeleton=Skeleton.read(f)
        skeleton.name_bones(name_list)
        skeleton.print()

        #LOD data
        LOD_num=read_uint32(f)
        LODs=[]
        for i in range(LOD_num):
            lod=SkeletalLOD.read(f, ff7r=ff7r)
            lod.print(str(i), skeleton.bones)
            LODs.append(lod)

        #mesh data?
        if ff7r:
            has_phy = read_uint32(f)
            if has_phy:
                phy_mesh=PhysicalMesh.read(f, skeleton.bones)
                phy_mesh.print()
            else:
                phy_mesh=None
        else:
            phy_mesh=None
        return SkeletalMesh(ff7r, unk, materials, skeleton, LODs, phy_mesh)

    def write(f, skeletalmesh):
        f.write(skeletalmesh.unk)
        write_array(f, skeletalmesh.materials, SkeletalMaterial.write, with_length=True)
        Skeleton.write(f, skeletalmesh.skeleton)
        write_array(f, skeletalmesh.LODs, SkeletalLOD.write, with_length=True)
        if skeletalmesh.ff7r:
            if skeletalmesh.phy_mesh is not None:
                write_uint32(f, 1)
                PhysicalMesh.write(f, skeletalmesh.phy_mesh)
            else:
                write_uint32(f, 0)


    def import_LODs(self, skeletalmesh, imports, name_list, file_data_ids, only_mesh=False, only_phy_bones=False,
                    dont_remove_KDI=False):
        if not self.ff7r:
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
            if self.phy_mesh is not None:
                self.phy_mesh.update_bone_ids(self.skeleton.bones)

        ignore_material_names=False
        if len(self.materials)<len(skeletalmesh.materials):
            ignore_material_names=True
            added_num = len(skeletalmesh.materials)-len(self.materials)
            for i in range(added_num):
                self.add_material_slot(imports, name_list, file_data_ids, skeletalmesh.materials[len(self.materials)])
            logger.warn('Added {} materials. You may need to edit name table to use the new materials.'.format(added_num))

        super().import_LODs(skeletalmesh, imports, name_list, file_data_ids, ignore_material_names=ignore_material_names)

        if not dont_remove_KDI:
            self.remove_KDI()

    def remove_KDI(self):
        if not self.ff7r:
            raise RuntimeError("The file should be an FF7R's asset!")
        
        for lod in self.LODs:
            lod.remove_KDI()

        logger.log("KDI buffers have been removed.")

    def save_as_gltf(self, name, save_folder):
        bones = Bone.bones_to_gltf(self.skeleton.bones)
        material_names = [m.import_name for m in self.materials]
        material_ids, uv_num = self.LODs[0].get_meta_for_blender()
        #gltf = glTF(bones, material_names, material_ids, uv_num)
        normals, tangents, positions, texcoords, joints, weights, joints2, weights2, indices = self.LODs[0].parse_buffers_for_gltf()
        #gltf.set_parsed_buffers(normals, tangents, positions, texcoords, joints, weights, joints2, weights2, indices)
        #gltf.save(name, save_folder)

    def import_gltf(self, gltf, imports, name_list, file_data_ids, only_mesh = True, ignore_material_names=True):
        if not self.ff7r:
            raise RuntimeError("The file should be an FF7R's asset!")
        bones = [Bone.gltf_to_bone(bone) for bone in gltf.bones]

        bone_diff=len(self.skeleton.bones)-len(bones)
        if (only_mesh) and bone_diff!=0:
            msg = 'Skeletons are not the same.'
            raise RuntimeError(msg)
        if not only_mesh:
            raise RuntimeError('Bone injection is not supported for glTF.')
            #self.skeleton.import_bones(bones, name_list)
        #if not only_mesh and self.phy_mesh is not None:
            #self.phy_mesh.update_bone_ids(self.skeleton.bones)

        ignore_material_names=False
        if len(self.materials)<len(gltf.materials):
            ignore_material_names=True
            added_num = len(gltf.materials)-len(self.materials)
            for i in range(added_num):
                self.add_material_slot(imports, name_list, file_data_ids, gltf.materials[len(self.materials)].name)
            logger.warn('Added {} materials. You need to edit name table to use the new materials.'.format(added_num))

        for m in gltf.materials:
            m.import_name = m.name
        new_material_ids = Material.check_confliction(self.materials, gltf.materials, ignore_material_names=ignore_material_names)
        
        self.remove_LODs()
        lod = self.LODs[0]
        lod.import_gltf(gltf)
        lod.update_material_ids(new_material_ids)
        pass

#collider or something? low poly mesh.
class PhysicalMesh:
    #vertices
    #bone_id: vertex group? each vertex has a bone id.
    #faces

    def __init__(self, f, bones):
        self.offset=f.tell()
        self.names = [b.name for b in bones]
        vertex_num=read_uint32(f)
        self.vb=f.read(vertex_num*12)

        num = read_uint32(f)
        check(num, vertex_num, f, 'Parse failed! (PhysicalMesh:vertex_num)')
        
        self.weight_buffer=list(struct.unpack('<'+'HHHHBBBB'*num, f.read(num*12)))
        #for i in range(len(self.weight_buffer)//8):
        #    id = self.weight_buffer[i*8]
        #   if id>0:
        #       print(id)
        #       print(bones[id].name)

        face_num=read_uint32(f)
        self.ib=f.read(face_num*6)

    def update_bone_ids(self, new_bones):
        new_bone_names = [b.name for b in new_bones]
        id_map = [0]*len(self.names)
        missing_bones = []
        for name, i in zip(self.names, range(len(self.names))):
            if name not in new_bone_names:
                missing_bones.append(name)
                continue
            id_map[i]=new_bone_names.index(name)
        if len(missing_bones)>0:
            if len(missing_bones)>10:
                logger.warn('Some existing bones are missing. It might corrupt animations. {}'.format(missing_bones[:10] + ['...']))
            else:
                logger.warn('Some existing bones are missing. It might corrupt animations. {}'.format(missing_bones))
            return

        ids = [self.weight_buffer[i*8:i*8+8] for i in range(len(self.vb)//12)]
        def update(ids):
            for i in range(4):
                ids[i]=id_map[ids[i]]
                if ids[i+4]==0:
                    break
            return ids
        ids = [update(i) for i in ids]
        self.weight_buffer=[x for row in ids for x in row]

    def read(f, bones):
        return PhysicalMesh(f, bones)

    def write(f, mesh):
        vertex_num = len(mesh.vb)//12
        write_uint32(f, vertex_num)
        f.write(mesh.vb)
        write_uint32(f, vertex_num)
        f.write(struct.pack('<'+'HHHHBBBB'*vertex_num, *mesh.weight_buffer))

        #f.write(mesh.weight_buffer)
        write_uint32(f, len(mesh.ib)//6)
        f.write(mesh.ib)

    def print(self, padding=0):
        pad=' '*padding
        logger.log(pad+'Mesh (offset: {})'.format(self.offset))
        logger.log(pad+'  vertex_num: {}'.format(len(self.vb)//12))
        logger.log(pad+'  face_num: {}'.format(len(self.ib)//6))
