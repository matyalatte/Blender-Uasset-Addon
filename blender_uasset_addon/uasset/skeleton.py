from ..util.io_util import *
from ..util.logger import logger
#from ..gltf.bone import Bone as gltfBone
#from ..gltf.gltf import glTF
import struct

class Bone:
    #name_id: id of name list
    #parent: parent bone's id
    #rot: quaternion
    #pos: position
    #size: size

    def __init__(self, name_id, instance, parent):
        self.name_id = name_id
        self.instance = instance
        self.parent = parent
        self.pos = None
        self.name = None
        self.parent_name = None
        self.children = []

    def read(f):
        name_id=read_uint32(f)
        instance = read_int32(f) #null?
        parent = read_int32(f)
        return Bone(name_id, instance, parent)

    def read_pos(self, f):
        ary = read_float32_array(f, 10)
        self.rot = ary[0:4]
        self.trans = ary[4:7]
        self.scale = ary[7:]

    def write(f, bone):
        write_uint32(f, bone.name_id)
        write_int32(f, bone.instance)
        write_int32(f, bone.parent)

    def write_pos(f, bone):
        write_float32_array(f, bone.rot+bone.trans+bone.scale)

    def update(self, bone):
        self.pos=bone.pos
        self.name = bone.name
        self.instance = bone.instance
        self.parent_name = bone.parent_name

    def update_name_id(self, name_list):
        if self.name_id>=0:
            name_list[self.name_id]=self.name
        else:
            self.name_id=len(name_list)
            #print("added name {}: {}".format(len(name_list), self.name))
            name_list.append(self.name)

    def print_bones(bones, padding=2):
        pad=' '*padding
        i=0
        for b in bones:
            logger.log(pad+'id: '+str(i)+', name: '+b.name+', parent: '+b.parent_name)
            i+=1

    def name_bones(bones, name_list):
        def name(bone):
            bone.name = name_list[bone.name_id]
        [name(b) for b in bones]
        for b in bones:
            parent_id = b.parent
            if parent_id!=-1:
                parent_name=bones[parent_id].name
            else:
                parent_name='None'
            b.parent_name = parent_name

    def get_bone_id(bones, bone_name):
        id=-1
        i=0
        for b in bones:
            if b.name==bone_name:
                id=i
                break
            i+=1
        return id

    def record_children(bones):
        children=[[] for i in range(len(bones))]
        bone_names = [b.name for b in bones]
        for b in bones:
            if b.parent_name=='None':
                continue
            children[bone_names.index(b.parent_name)].append(bone_names.index(b.name))
        for b, c in zip(bones, children):
            b.children=c

    def to_gltf_bone(self):
        ary = list(struct.unpack('<'+'f'*10, self.pos))
        children = [c+1 for c in self.children]
        rot = [-ary[0], -ary[2], -ary[1], ary[3]]
        trans = ary[4:7]
        trans = [trans[0]/100, trans[2]/100, trans[1]/100]
        scale = [ary[7], ary[9], ary[8]]
        #return gltfBone(self.name, children, rot, trans, scale)

    def gltf_to_bone(gltf_bone):
        rot = gltf_bone.rot
        rot = [-rot[0], -rot[2], -rot[1], rot[3]]
        trans = gltf_bone.trans
        trans = [trans[0]*100, trans[2]*100, trans[1]*100]
        scale = [1]*3
        ary = rot+trans+scale
        bone = Bone(-1, 0, -1)
        bone.pos = struct.pack('<'+'f'*10, *ary)
        bone.name = gltf_bone.name
        bone.parent_name = gltf_bone.parent_name
        return bone

    def bones_to_gltf(bones):
        Bone.record_children(bones)
        gltf_bones = [b.to_gltf_bone() for b in bones]
        return gltf_bones

    def copy(self):
        bone = Bone(self.name_id, self.instance, self.parent)
        bone.name = self.name
        bone.pos = self.pos
        bone.parent_name = self.parent_name
        return bone

    def update_parent_id(self, bones):
        if self.parent_name=='None':
            self.parent = -1
            return
        for b, i in zip(bones, range(len(bones))):
            if b.name == self.parent_name:
                self.parent = i
                break

#Skeleton data for skeletal mesh assets
class Skeleton:
    #bones: bone data
    #bones2: there is more bone data. I don't known how it works.

    def __init__(self, f):
        self.offset=f.tell()
        self.bones = read_array(f, Bone.read)

        #read position
        bone_num=read_uint32(f)
        check(bone_num, len(self.bones), f, 'Parse failed! Invalid bone number detected. Have you named the armature "Armature"?')
        for b in self.bones:
            b.read_pos(f)


        read_const_uint32(f, len(self.bones))
        for b, i in zip(self.bones, range(len(self.bones))):
            read_const_uint32(f, b.name_id)
            read_null(f)
            read_const_uint32(f, i)

        #self.name_to_index_map=read_array(f, Bone.read)

    def read(f):
        return Skeleton(f)

    def write(f, skeleton):
        write_array(f, skeleton.bones, Bone.write, with_length=True)
        write_array(f, skeleton.bones, Bone.write_pos, with_length=True)
        write_uint32(f, len(skeleton.bones))
        for b, i in zip(skeleton.bones, range(len(skeleton.bones))):
            write_uint32(f, b.name_id)
            write_null(f)
            write_uint32(f, i)

    def name_bones(self, name_list):
        Bone.name_bones(self.bones, name_list)
        Bone.record_children(self.bones)

    def import_bones(self, bones, name_list, only_phy_bones=False):
        old_bone_num = len(self.bones)
        if len(self.bones)<len(bones):
            self.bones += [Bone(-1, None, None) for i in range(len(bones)-len(self.bones))]
        for self_bone, new_bone in zip(self.bones, bones):
            #if self_bone.name!=new_bone.name:
            #    raise RuntimeError("")
            #print('{} -> {}'.format(self_bone.pos[4:7], new_bone.pos[4:7]))
            if only_phy_bones and 'Phy' not in new_bone.name:
                continue
            self_bone.update(new_bone)
        self.bones = self.bones[:len(bones)]
        if only_phy_bones:
            #logger.log('Imported bones: {}'.format(bone_list))
            logger.log('Phy bones have been imported.', ignore_verbose=True)
        else:
            logger.log('Skeleton has been imported. (bones:{}->{})'.format(old_bone_num, len(self.bones)), ignore_verbose=True)

        for bone in self.bones:
            bone.update_name_id(name_list)
        for bone in self.bones:
            bone.update_parent_id(bones)

    def print(self, padding=0):
        pad=' '*padding
        logger.log(pad+'Skeleton (offset: {})'.format(self.offset))
        logger.log(pad+'  bone_num: {}'.format(len(self.bones)))
        Bone.print_bones(self.bones, padding=2+padding)

#Skeleton data for skeleton assets (*_Skeleton.uexp)
class SkeletonAsset:
    #bones: bone data
    #bones2: there is more bone data. I don't known how it works.

    MAGIC = b'\x00\x02\x01\x02\x01\x03'
    def __init__(self, f, name_list):
        self.offset=f.tell()
        magic = f.read(6)
        check(magic, SkeletonAsset.MAGIC, f, "Not FF7R's asset.")
        bone_num = read_uint32(f)
        unk = f.read(bone_num*3)
        check(unk, b'\x82\x03\x01'*bone_num, f)
        self.guid = f.read(16)
        self.unk_ids = read_uint32_array(f)
        read_null(f)
        
        self.bones = read_array(f, Bone.read)

        #read position
        bone_num=read_uint32(f)
        check(bone_num, len(self.bones), f, 'Parse failed! Invalid bone number detected. Have you named the armature "Armature"?')
        for b in self.bones:
            b.read_pos(f)
        
        read_const_uint32(f, len(self.bones))
        for b, i in zip(self.bones, range(len(self.bones))):
            read_const_uint32(f, b.name_id)
            read_null(f)
            read_const_uint32(f, i)

        #self.name_to_index_map=read_array(f, Bone.read)

        self.name_bones(name_list)
        self.print()

    def read(f, name_list):
        return SkeletonAsset(f, name_list)

    def write(f, skeleton):
        f.write(SkeletonAsset.MAGIC)
        bone_num = len(skeleton.bones)
        write_uint32(f, bone_num)
        f.write(b'\x82\x03\x01'*bone_num)
        f.write(skeleton.guid)
        write_uint32_array(f, skeleton.unk_ids, with_length=True)
        write_null(f)
        write_array(f, skeleton.bones, Bone.write, with_length=True)
        write_array(f, skeleton.bones, Bone.write_pos, with_length=True)
        write_uint32(f, len(skeleton.bones))
        for b, i in zip(skeleton.bones, range(len(skeleton.bones))):
            write_uint32(f, b.name_id)
            write_null(f)
            write_uint32(f, i)

    def name_bones(self, name_list):
        Bone.name_bones(self.bones, name_list)
        Bone.record_children(self.bones)

    def import_bones(self, bones, name_list, only_phy_bones=False):
        old_bone_num = len(self.bones)
        new_bones = []
        for new_bone in bones:
            name = new_bone.name
            if only_phy_bones and 'Phy' not in name:
                continue
            updated=False
            for self_bone in self.bones:
                if self_bone.name==name:
                    self_bone.pos = new_bone.pos
                    self_bone.parent_name = new_bone.parent_name
                    updated=True
                    break
            if not updated:
                copied_bone = new_bone.copy()
                copied_bone.name_id = -1
                copied_bone.update_name_id(name_list)
                new_bones.append(copied_bone)
        self.bones += new_bones
        for b in self.bones:
            b.update_parent_id(self.bones)

        if only_phy_bones:
            logger.log('Phy bones have been imported.', ignore_verbose=True)
        else:
            logger.log('Skeleton has been imported. (bones:{}->{})'.format(old_bone_num, len(self.bones)), ignore_verbose=True)

    def print(self, padding=0):
        pad=' '*padding
        logger.log(pad+'Skeleton (offset: {})'.format(self.offset))
        logger.log(pad+'  bone_num: {}'.format(len(self.bones)))
        Bone.print_bones(self.bones, padding=2+padding)

    def to_gltf_bones(self):
        Bone.record_children(self.bones)
        gltf_bones = [b.to_gltf_bone() for b in self.bones]
        return gltf_bones

    def save_as_gltf(self, name, save_folder):
        bones = Bone.bones_to_gltf(self.bones)
        #gltf = glTF(bones, None, None, None)
        #gltf.save(name, save_folder)
    