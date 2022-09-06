"""Classes for skeleton data."""
from ..util import io_util as io


class Bone:
    """Bone.

    Attributes:
        name_id (int): id of name list
        name (string): bone name
        parent (int): parent bone's id
        parent_name (string): bone name for parent bone
        children (list[int]): child bone ids
        trans (list[float]): position
        rot (list[float]): rotation (x,y,z,w)
        size (list[float]): size
    """
    def __init__(self, name_id, instance, parent):
        """Constructor."""
        self.name_id = name_id
        self.instance = instance
        self.parent = parent
        self.name = None
        self.parent_name = None
        self.children = []
        self.trans = None
        self.rot = None
        self.scale = None

    @staticmethod
    def read(f):
        """Read function."""
        name_id = io.read_uint32(f)
        instance = io.read_int32(f)
        parent = io.read_int32(f)
        return Bone(name_id, instance, parent)

    def read_pos(self, f, version):
        """Read TRS."""
        if version >= '5.0':
            ary = io.read_float64_array(f, 10)
        else:
            ary = io.read_float32_array(f, 10)
        self.rot = ary[0:4]
        self.trans = ary[4:7]
        self.scale = ary[7:]

    def write(self, f):
        """Write function."""
        io.write_uint32(f, self.name_id)
        io.write_int32(f, self.instance)
        io.write_int32(f, self.parent)

    def write_pos(self, f, version):
        """Write TRS."""
        ary = self.rot + self.trans + self.scale
        if version >= '5.0':
            io.write_float64_array(f, ary)
        else:
            io.write_float32_array(f, ary)

    def update(self, bone):
        """Import bone data."""
        self.trans = bone.trans
        self.rot = bone.rot
        self.scale = bone.scale
        self.name = bone.name
        self.parent_name = bone.parent_name

    def update_name_id(self, name_list):
        """Add new name to list if it doesn't exist."""
        if self.name_id >= 0:
            name_list[self.name_id] = self.name
        else:
            self.name_id = len(name_list)
            # print("added name {}: {}".format(len(name_list), self.name))
            name_list.append(self.name)

    @staticmethod
    def print_bones(bones, padding=2):
        """Print bone data."""
        pad = ' ' * padding
        i = 0
        for bone in bones:
            print(pad + f'id: {i}, name: {bone.name}, parent: {bone.parent_name}')
            i += 1

    @staticmethod
    def name_bones(bones, name_list):
        """Convert name ids to bone names."""
        def name(bone):
            bone_name = name_list[bone.name_id]
            if bone.instance != 0:
                bone_name += '.' + str(bone.instance).zfill(3)
            bone.name = bone_name
        list(map(name, bones))
        for b in bones:
            parent_id = b.parent
            if parent_id != -1:
                parent_name = bones[parent_id].name
                parent_obj = bones[parent_id]
            else:
                parent_name = 'None'
                parent_obj = None
            b.parent_name = parent_name
            b.parent_obj = parent_obj

    @staticmethod
    def get_bone_id(bones, bone_name):
        """Get bone ids from name."""
        index = -1
        i = 0
        for bone in bones:
            if bone.name == bone_name:
                index = i
                break
            i += 1
        return index

    @staticmethod
    def record_children(bones):
        """Store child bone ids."""
        children = [[] for i in range(len(bones))]
        bone_names = [b.name for b in bones]
        for b in bones:
            if b.parent_name == 'None':
                continue
            children[bone_names.index(b.parent_name)].append(bone_names.index(b.name))
        for b, c in zip(bones, children):
            b.children = c

    def update_parent_id(self, bones):
        """Convert parent ids to bone names."""
        if self.parent_name == 'None':
            self.parent = -1
            return
        for b, i in zip(bones, range(len(bones))):
            if b.name == self.parent_name:
                self.parent = i
                break


class Skeleton:
    """Skeleton data for skeletal mesh assets."""
    # bones: bone data
    # bones2: there is more bone data. I don't known how it works.

    def __init__(self, f, version):
        """Read function."""
        self.offset = f.tell()
        self.version = version
        self.bones = io.read_array(f, Bone.read)

        # read position
        bone_num = io.read_uint32(f)
        io.check(bone_num, len(self.bones), f)
        for bone in self.bones:
            bone.read_pos(f, version)

        # read NameToIndexMap
        io.read_const_uint32(f, len(self.bones))
        for bone, i in zip(self.bones, range(len(self.bones))):
            io.read_const_uint32(f, bone.name_id)
            io.read_const_uint32(f, bone.instance)
            io.read_const_uint32(f, i)

    @staticmethod
    def read(f, version):
        """Read function."""
        return Skeleton(f, version)

    def write(self, f):
        """Write function."""
        io.write_array(f, self.bones, with_length=True)
        io.write_uint32(f, len(self.bones))
        list(map(lambda x: x.write_pos(f, self.version), self.bones))
        io.write_uint32(f, len(self.bones))
        for bone, i in zip(self.bones, range(len(self.bones))):
            io.write_uint32(f, bone.name_id)
            io.write_uint32(f, bone.instance)
            io.write_uint32(f, i)

    def name_bones(self, name_list):
        """Convert bone ids to names."""
        Bone.name_bones(self.bones, name_list)
        Bone.record_children(self.bones)

    def import_bones(self, bones, name_list):
        """Import bone data."""
        old_bone_num = len(self.bones)
        if len(self.bones) < len(bones):
            self.bones += [Bone(-1, 0, None) for i in range(len(bones) - len(self.bones))]
        for self_bone, new_bone in zip(self.bones, bones):
            # if self_bone.name!=new_bone.name:
            #     raise RuntimeError("")
            # print('{} -> {}'.format(self_bone.pos[4:7], new_bone.pos[4:7]))
            # if only_phy_bones and 'Phy' not in new_bone.name:
            #     continue
            self_bone.update(new_bone)
        self.bones = self.bones[:len(bones)]
        # if only_phy_bones:
        #     print('Phy bones have been imported.')
        print(f'Updated skeleton (bones:{old_bone_num}->{len(self.bones)})')

        for bone in self.bones:
            bone.update_name_id(name_list)
        for bone in self.bones:
            bone.update_parent_id(bones)

    def print(self, padding=0):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'Skeleton (offset: {self.offset})')
        print(pad + f'  bone_num: {len(self.bones)}')
        Bone.print_bones(self.bones, padding=2 + padding)


class SkeletonAsset:
    """Skeleton data for skeleton assets (*_Skeleton.uexp)."""
    def __init__(self, f, version, name_list, verbose=False):
        """Read function."""
        self.offset = f.tell()
        self.version = version
        binary = f.read(4)
        while binary != b'\xff' * 4:
            if b'\xff' not in binary:
                binary = f.read(4)
            else:
                binary = b''.join([binary[1:], f.read(1)])
            if f.tell() > 500000:
                raise RuntimeError('failed to parse')
        offset = f.tell() - 16 - self.offset
        f.seek(self.offset)
        self.unk = f.read(offset)

        self.bones = io.read_array(f, Bone.read)

        # read position
        bone_num = io.read_uint32(f)
        io.check(bone_num, len(self.bones), f)
        for b in self.bones:
            b.read_pos(f, version)

        io.read_const_uint32(f, len(self.bones))
        for b, i in zip(self.bones, range(len(self.bones))):
            io.read_const_uint32(f, b.name_id)
            io.read_const_uint32(f, b.instance)
            io.read_const_uint32(f, i)

        # self.name_to_index_map=read_array(f, Bone.read)

        self.name_bones(name_list)

        if verbose:
            self.print()

    @staticmethod
    def read(f, version, name_list, verbose=False):
        """Read function."""
        return SkeletonAsset(f, version, name_list, verbose=verbose)

    def write(self, f):
        """Write function."""
        f.write(self.unk)
        io.write_array(f, self.bones, with_length=True)
        io.write_uint32(f, len(self.bones))
        list(map(lambda x: x.write_pos(f, self.version), self.bones))
        io.write_uint32(f, len(self.bones))
        for bone, i in zip(self.bones, range(len(self.bones))):
            io.write_uint32(f, bone.name_id)
            io.write_uint32(f, bone.instance)
            io.write_uint32(f, i)

    def name_bones(self, name_list):
        """Convert bone ids to names, and store child bone ids."""
        Bone.name_bones(self.bones, name_list)
        Bone.record_children(self.bones)

    def import_bones(self, bones, name_list):
        """Import bone data."""
        old_bone_num = len(self.bones)
        new_bones = []
        for new_bone in bones:
            name = new_bone.name
            # if only_phy_bones and 'Phy' not in name:
            #     continue
            updated = False
            for self_bone in self.bones:
                if self_bone.name == name:
                    self_bone.update(new_bone)
                    updated = True
                    break
            if not updated:
                bone = Bone(-1, 0, None)
                bone.update(new_bone)
                bone.update_name_id(name_list)
                new_bones.append(bone)
        self.bones += new_bones
        for b in self.bones:
            b.update_parent_id(self.bones)

        # if only_phy_bones:
        #     print('Phy bones have been imported.')
        print(f'Updated skeleton (bones:{old_bone_num}->{len(self.bones)})')

    def print(self, padding=0):
        """Print meta data."""
        pad = ' ' * padding
        print(pad + f'Skeleton (offset: {self.offset})')
        print(pad + f'  bone_num: {len(self.bones)}')
        Bone.print_bones(self.bones, padding=2 + padding)
