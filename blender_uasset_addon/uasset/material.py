from ..util.io_util import *
from ..util.logger import logger

#Base class for material
class Material:
    def __init__(self, import_id, slot_name_id, bin):
        self.import_id=import_id
        self.slot_name_id=slot_name_id
        self.bin=bin

    def read(f):
        pass

    def write(f, material):
        pass

    def print_materials(materials, name_list, imports, offset):
        logger.log('Materials (offset: {})'.format(offset))
        for material in materials:
            material.slot_name=name_list[material.slot_name_id]
            material.import_name=imports[-material.import_id-1].name
            material.file_path = imports[-material.import_id-1].parent_name
            material.print()

    def print(self, padding=2):
        pad=' '*padding
        logger.log(pad+self.import_name)
        logger.log(pad+'  slot name: {}'.format(self.slot_name))
        logger.log(pad+'  file path: {}'.format(self.file_path))

    def check_confliction(materials1, materials2, ignore_material_names=False):
        def get_range(num):
            return [i for i in range(num)]

        new_material_ids = get_range(len(materials2))

        if ignore_material_names:
            logger.log('Material names have been ignored.')
            return new_material_ids

        material_names1 = [mat1.import_name for mat1 in materials1]
        material_names2 = [mat2.import_name for mat2 in materials2]
        if len(material_names1)!=len(list(set(material_names1))) or len(material_names2)!=len(list(set(material_names2))):
            logger.warn('Material name conflicts detected. Materials might not be assigned correctly.')
            return new_material_ids

        resolved_mat1 = [False for i in range(len(materials1))]
        unresolved_mat2 = []
        for mat2, i in zip(material_names2, get_range(len(materials2))):
            found = False
            
            for mat1, j in zip(material_names1, get_range(len(materials1))):
                if mat1==mat2:
                    new_material_ids[i]=j
                    resolved_mat1[j]=True
                    found=True
                    break
            if not found:
                unresolved_mat2.append((mat2, i))

        unresolved_count = 0
        for f in resolved_mat1:
            if not f:
                unresolved_count+=1

        if len(unresolved_mat2)==1 and unresolved_count==1:
            new_material_ids[unresolved_mat2[0][1]]=resolved_mat1.index(False)
            unresolved_mat2 = []
            
        if len(unresolved_mat2)!=0:
            mat2=unresolved_mat2[0][0]
            logger.warn('Material name conflicts detected. Materials might not be assigned correctly. ({})'.format(mat2))
            return get_range(len(materials2))

        if new_material_ids!=get_range(len(materials2)):
            logger.log('Material name conflicts detected. But it has been resolved correctly.')
        return new_material_ids

#material for static mesh
class StaticMaterial(Material):
    def read(f):
        f.seek(2, 1)
        import_id=read_int32(f)
        slot_name_id=read_uint32(f)
        #bin=f.read(24)
        return StaticMaterial(import_id, slot_name_id, None)

    def write(f, material):
        f.write(b'\x00\x07')
        write_int32(f, material.import_id)
        write_uint32(f, material.slot_name_id)
        f.write(material.bin)

    def copy(self):
        return StaticMaterial(self.import_id, self.slot_name_id, b''.join([self.bin]))


#material for skeletal mesh
class SkeletalMaterial(Material):
    def read(f):
        import_id=read_int32(f)
        slot_name_id=read_uint32(f)
        bin=f.read(28) #cast shadow, uv density?
        return SkeletalMaterial(import_id, slot_name_id, bin)

    def write(f, material):
        write_int32(f, material.import_id)
        write_uint32(f, material.slot_name_id)
        f.write(material.bin)

    def copy(self):
        return SkeletalMaterial(self.import_id, self.slot_name_id, b''.join([self.bin]))
