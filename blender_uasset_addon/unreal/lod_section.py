from ..util.io_util import *
from ..util.logger import logger

#Base class for LOD sections
class LODSection:
    def __init__(self):
        self.material_id = None

    def update_material_ids(self, new_material_ids):
        self.material_id=new_material_ids[self.material_id]

#LOD section for static mesh
class StaticLODSection(LODSection):
    def __init__(self, f):
        self.material_id = read_uint32(f)
        self.first_ib_id = read_uint32(f)
        self.face_num = read_uint32(f)
        self.first_vertex_id = read_uint32(f)
        self.last_vertex_id = read_uint32(f)
        self.enable_collision = read_uint32(f)
        self.cast_shadow = read_uint32(f)

    def read(f):
        return StaticLODSection(f)

    def write(f, section):
        write_uint32(f, section.material_id)
        write_uint32(f, section.first_ib_id)
        write_uint32(f, section.face_num)
        write_uint32(f, section.first_vertex_id)
        write_uint32(f, section.last_vertex_id)
        write_uint32(f, section.enable_collision)
        write_uint32(f, section.cast_shadow)

    def import_section(self, section):
        self.not_first = section.not_first
        self.material_id=section.material_id
        self.first_ib_id=section.first_ib_id
        self.face_num=section.face_num
        self.first_vertex_id=section.first_vertex_id
        self.last_vertex_id=section.last_vertex_id
        self.enable_collision=section.enable_collision
        self.cast_shadow=section.cast_shadow

    def print(self, i, padding=2):
        pad = ' '*padding
        logger.log(pad+'section{}'.format(i))
        logger.log(pad+'  material_id: {}'.format(self.material_id))
        logger.log(pad+'  first_ib_id: {}'.format(self.first_ib_id))
        logger.log(pad+'  face_num: {}'.format(self.face_num))
        logger.log(pad+'  first_vertex_id: {}'.format(self.first_vertex_id))
        logger.log(pad+'  last_vertex_id: {}'.format(self.last_vertex_id))
        logger.log(pad+'  enable_collision: {}'.format(self.enable_collision>0))
        logger.log(pad+'  cast_shadow: {}'.format(self.cast_shadow>0))

#LOD section for skeletal mesh
class SkeletalLODSection(LODSection):
    # material_id: material id
    # first_ib_id: Where this section start in face data.
    # face_num: the number of faces in this section
    # first_vertex_id: Where this section start in vertex data.
    # vertex_group: Id of weight painted bones. Bone influences are specified by vertex_group's id (not bone id).
    # vertex_num: the number of vertices in this section

    UNK=b'\x00\xFF\xFF'
    CorrespondClothAssetIndex=b'\xCD\xCD'

    def __init__(self, ff7r, material_id, first_ib_id, face_num, unk, \
                first_vertex_id, vertex_group, vertex_num, max_bone_influences, \
                unk1, unk2):
        self.ff7r = ff7r
        self.material_id = material_id
        self.first_ib_id = first_ib_id
        self.face_num = face_num
        self.unk = unk
        self.first_vertex_id = first_vertex_id
        self.vertex_group = vertex_group
        self.vertex_num = vertex_num
        self.max_bone_influences = max_bone_influences
        self.unk1 = unk1
        self.unk2 = unk2  
            
    def read(f, ff7r=False):
        one = read_uint16(f)
        check(one, 1, f, 'Parse failed! (LOD_Section:StripFlags)')
        material_id=read_uint16(f)

        first_ib_id=read_uint32(f)

        face_num = read_uint32(f)
        read_null(f, 'Parse failed! (LOD_Section:Number of Faces)')
        unk=f.read(3)
        check(unk, SkeletalLODSection.UNK, f, 'Parse failed! (LOD_Section:1)')
        unk=f.read(1)
        read_null(f, 'Parse failed! (LOD_Section:2)')
        read_const_uint32(f, 1, 'Parse failed! (LOD_Section:3)')
        first_vertex_id=read_uint32(f)

        vertex_group=read_uint16_array(f)

        vertex_num=read_uint32(f)

        max_bone_influences=read_uint32(f)

        read_null_array(f, 3, 'Parse failed! (LOD_Section:4)')
        cloth_asset_index=f.read(2)
        check(cloth_asset_index, SkeletalLODSection.CorrespondClothAssetIndex, f, 'Parse failed! (LOD_Section:CorrespondClothAssetIndex)')
        read_null_array(f,4, 'LOD_Section:ClothingSectionData: GUID should be null.')
        unknown=read_int32(f)
        check(unknown, -1, f, 'LOD_Section:ClothingSectionData: AssetLodIndex should be -1.')
        if ff7r:
            unk1=read_uint32(f)
            num=read_uint32(f)
            unk2=read_uint8_array(f, len=num*16)
        else:
            unk1=None
            unk2=None
        section=SkeletalLODSection(ff7r, material_id, first_ib_id, face_num, unk, \
                    first_vertex_id, vertex_group, vertex_num, max_bone_influences, \
                    unk1, unk2)
        return section

    def copy(self):
        return SkeletalLODSection(self.ff7r, self.material_id, self.first_ib_id, self.face_num, self.unk, \
                    self.first_vertex_id, self.vertex_group, self.vertex_num, self.max_bone_influences, \
                    0, [])

    def write(f, section):
        write_uint16(f, 1)
        write_uint16(f, section.material_id)
        write_uint32(f, section.first_ib_id)
        write_uint32(f, section.face_num)
        write_null(f)
        f.write(SkeletalLODSection.UNK)
        f.write(section.unk)
        write_uint32_array(f,[0,1])
        write_uint32(f, section.first_vertex_id)
        write_uint16_array(f, section.vertex_group, with_length=True)
        write_uint32(f, section.vertex_num)
        write_uint32(f, section.max_bone_influences)
        write_null_array(f,3)
        f.write(SkeletalLODSection.CorrespondClothAssetIndex)
        write_null_array(f, 4)
        write_int32(f,-1)
        if section.ff7r:
            write_uint32(f, section.unk1)
            write_uint32(f, len(section.unk2)//16)
            write_uint8_array(f, section.unk2)

    def import_section(self, section):
        self.material_id=section.material_id
        self.first_ib_id=section.first_ib_id
        self.face_num=section.face_num
        self.vertex_group=section.vertex_group
        self.first_vertex_id=section.first_vertex_id
        self.vertex_num=section.vertex_num
        self.max_bone_influences=section.max_bone_influences
        self.unk=section.unk

    def remove_KDI(self):
        self.unk1=0
        self.unk2=[]

    def bone_ids_to_name(bone_ids, bones):
        bone_name_list=[bones[id].name for id in bone_ids]
        return bone_name_list

    def print(self, name, bones, padding=2):
        pad = ' '*padding
        logger.log(pad+'section '+name)
        logger.log(pad+'  material_id: {}'.format(self.material_id))
        logger.log(pad+'  first_ib_id: {}'.format(self.first_ib_id))
        logger.log(pad+'  face_num: {}'.format(self.face_num))
        logger.log(pad+'  first_vertex_id: {}'.format(self.first_vertex_id))
        vg_name=SkeletalLODSection.bone_ids_to_name(self.vertex_group, bones)
        logger.log(pad+'  vertex_group: {}'.format(vg_name))
        logger.log(pad+'  vertex_num: {}'.format(self.vertex_num))
        logger.log(pad+'  max bone influences: {}'.format(self.max_bone_influences))
        if self.unk2 is not None:
            logger.log(pad+'  KDI flag: {}'.format(self.unk1==True))
            logger.log(pad+'  vertices influenced by KDI: {}'.format(len(self.unk2)//16))

    def import_from_blender(self, vertex_group, material_id, first_vertex_id, vertex_num, first_ib_id, face_num, max_bone_influences):
        self.material_id = material_id
        self.vertex_group = vertex_group

        self.first_ib_id=first_ib_id
        self.face_num=face_num
        self.first_vertex_id=first_vertex_id
        self.vertex_num=vertex_num
        self.max_bone_influences=max_bone_influences
        #self.unk=section.unk
