from ..util.io_util import *

from .lod_section import StaticLODSection, SkeletalLODSection, SkeletalLODSection5
from .buffer import *

#Base class for LOD
class LOD:
    def __init__(self, vb, vb2, ib, ib2, color_vb=None):
        self.vb = vb
        self.vb2 = vb2
        self.ib = ib
        self.ib2 = ib2
        self.color_vb = color_vb

    def import_LOD(self, lod, name=''):
        #if len(self.sections)<len(lod.sections):
        #    raise RuntimeError('too many materials')
        f_num1=self.ib.size//3
        f_num2=lod.ib.size//3
        v_num1=self.vb.vertex_num
        v_num2=lod.vb.vertex_num
        uv_num1 = self.uv_num
        uv_num2 = lod.uv_num
        self.ib = lod.ib
        self.vb = lod.vb
        self.vb2 = lod.vb2
        self.ib2 = lod.ib2
        if self.color_vb is not None:
            self.color_vb = lod.color_vb
        self.uv_num = lod.uv_num
        print('LOD{} has been imported.'.format(name))
        print('  faces: {} -> {}'.format(f_num1, f_num2))
        print('  vertices: {} -> {}'.format(v_num1, v_num2))
        print('  uv maps: {} -> {}'.format(uv_num1, uv_num2))

    #get all buffers LOD has
    def get_buffers(self):
        buffers = [self.vb, self.vb2, self.ib, self.ib2]
        if self.color_vb is not None:
            buffers += [self.color_vb]
        return buffers

    #reorder material ids
    def update_material_ids(self, new_material_ids):
        for section in self.sections:
            section.update_material_ids(new_material_ids)

    def get_meta_for_blender(self):
        material_ids = [section.material_id for section in self.sections]
        return material_ids, self.uv_num

def split_list(l, first_ids):
    last_ids = first_ids[1:]+[len(l)]
    splitted = [l[first:last] for first, last in zip(first_ids, last_ids)]
    return splitted

def flatten(l):
    return [x for row in l for x in row]

#LOD for static mesh
class StaticLOD(LOD):
    def __init__(self, offset, sections, flags, vb, vb2, color_vb, ib, ib2, reversed_ib, reversed_ib2, adjacency_ib, unk):
        self.offset = offset
        self.sections = sections
        self.flags = flags
        self.uv_num = vb2.uv_num
        super().__init__(vb, vb2, ib, ib2, color_vb=color_vb)
        self.reversed_ib = reversed_ib
        self.reversed_ib2 = reversed_ib2
        self.adjacency_ib = adjacency_ib
        self.unk = unk
        self.face_num=0
        for section in self.sections:
            self.face_num+=section.face_num

    def read(f):
        offset = f.tell()
        one = read_uint16(f)
        check(one, 1, f)
        sections = read_array(f, StaticLODSection.read)

        flags = f.read(4)

        vb = PositionVertexBuffer.read(f, name='VB0') #xyz
        vb2 = StaticMeshVertexBuffer.read(f, name='VB2') #normals+uv_maps

        color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        ib = StaticIndexBuffer.read(f, name='IB') #IndexBuffer
        reversed_ib = StaticIndexBuffer.read(f, name='Reversed_IB') #ReversedIndexBuffer
        ib2 = StaticIndexBuffer.read(f, name='IB2') #DepathOnlyIndexBuffer
        reversed_ib2 = StaticIndexBuffer.read(f, name='Reversed_IB2') #ReversedDepthOnlyIndexBuffer
        adjacency_ib =StaticIndexBuffer.read(f, name='Adjacency_IB') #AdjacencyIndexBuffer
        unk = f.read(24)
        return StaticLOD(offset, sections, flags, vb, vb2, color_vb, ib, ib2, reversed_ib, reversed_ib2, adjacency_ib, unk)

    def write(f, lod):
        write_uint16(f, 1)
        write_array(f, lod.sections, StaticLODSection.write, with_length=True)
        f.write(lod.flags)
        PositionVertexBuffer.write(f, lod.vb)
        StaticMeshVertexBuffer.write(f, lod.vb2)

        ColorVertexBuffer.write(f, lod.color_vb)

        StaticIndexBuffer.write(f, lod.ib)
        StaticIndexBuffer.write(f, lod.reversed_ib)
        StaticIndexBuffer.write(f, lod.ib2)
        StaticIndexBuffer.write(f, lod.reversed_ib2)
        StaticIndexBuffer.write(f, lod.adjacency_ib)
        f.write(lod.unk)

    def print(self, i, padding=0):
        pad=' '*padding
        print(pad+'LOD{} (offset: {})'.format(i, self.offset))
        for j in range(len(self.sections)):
            self.sections[j].print(j, padding=padding+2)
        print(pad+'face_count: {}'.format(self.face_num))
        print(pad+'vertex_count: {}'.format(self.vb.vertex_num))
        print(pad+'uv_count: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            buf.print(padding=padding+2)

    def parse_buffers_for_blender(self):
        pos = self.vb.parse()
        normal, texcoords = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]

        ls = [normal, pos]
        normals, positions = [split_list(l, first_vertex_ids) for l in ls]

        texcoords = [split_list(l, first_vertex_ids) for l in texcoords]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i-first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        
        return normals, positions, texcoords, None, None, None, indices

    def import_from_blender(self, primitives):
        s_num1=len(self.sections)
        f_num1=self.ib.size//3
        v_num1=self.vb.vertex_num
        uv_num1 = self.uv_num

        uv_maps = primitives['UV_MAPS'] #(sction count, uv count, vertex count, 2)
        self.uv_num = len(uv_maps)
        #pos_range = self.vb.get_range()
        positions = primitives['POSITIONS']
        positions = positions
        self.vb.import_from_blender(positions)

        normals = primitives['NORMALS']
        
        material_ids = primitives['MATERIAL_IDS']
        indices = primitives['INDICES']

        if len(self.sections)<len(material_ids):
            self.sections += [self.sections[-1].copy() for i in range(len(material_ids)-len(self.sections))]
        self.sections=self.sections[:len(material_ids)]

        vertex_count = primitives['VERTEX_COUNTS']
        if self.color_vb.buf is not None:
            self.color_vb.update(sum(vertex_count))
        face_count = [len(ids)//3 for ids in indices]
        first_vertex_id = 0
        first_ids =[]
        first_ib_id = 0
        for section, id, vert_num, face_num in zip(self.sections, material_ids, vertex_count, face_count):
            first_ids.append(first_vertex_id)
            section.import_from_blender(id, first_vertex_id, vert_num, first_ib_id, face_num)
            first_vertex_id += vert_num
            first_ib_id += face_num*3

        self.vb2.import_from_blender(normals, uv_maps, self.uv_num)
        indices = [[i+first_id for i in ids] for ids, first_id in zip(indices, first_ids)]
        indices = flatten(indices)

        self.color_vb.disable()
        self.ib.update(indices, use_uint32=self.vb.size>65000)
        self.reversed_ib.disable()
        self.ib2.disable()
        self.reversed_ib2.disable()
        self.adjacency_ib.disable()

        s_num2=len(self.sections)
        f_num2=self.ib.size//3
        v_num2=self.vb.vertex_num
        uv_num2 = self.uv_num

        print('Updated LOD0')
        print('  sections: {} -> {}'.format(s_num1, s_num2))
        print('  faces: {} -> {}'.format(f_num1, f_num2))
        print('  vertices: {} -> {}'.format(v_num1, v_num2))
        print('  uv maps: {} -> {}'.format(uv_num1, uv_num2))


#LOD for skeletal mesh
class SkeletalLOD(LOD):

    def get_buffers(self):
        buffers = super().get_buffers()
        if self.KDI_buffer_size>0:
            buffers += [self.KDI_buffer, self.KDI_VB]
        return buffers

    def print(self, name, bones, padding=0):
        pad=' '*padding
        print(pad+'LOD '+name+' (offset: {})'.format(self.offset))
        for i in range(len(self.sections)):
            self.sections[i].print(str(i),bones, padding=padding+2)
        pad+=' '*padding
        print(pad+'face count: {}'.format(self.ib.size//3))
        print(pad+'vertex count: {}'.format(self.vb.vertex_num))
        print(pad+'uv count: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            if buf is not None:
                buf.print(padding=padding+2)

class SkeletalLOD4(SkeletalLOD):
    #sections: mesh data is separeted into some sections.
    #              each section has material id and vertex group.
    #active_bone_ids: maybe bone ids. but I don't know how it works.
    #bone_ids: active bone ids?
    #uv_num: the number of uv maps

    def read(f, version):
        return SkeletalLOD4(f, version)

    def __init__(self, f, version):
        self.offset=f.tell()
        self.version=version
        one = read_uint8(f)
        check(one, 1, f, 'Parse failed! (LOD:one)')
        no_tessellation = read_uint8(f)
        self.sections=[SkeletalLODSection.read(f, self.version) for i in range(read_uint32(f))]

        self.KDI_buffer_size=0
        for section in self.sections:
            if section.unk2 is not None:
                self.KDI_buffer_size+=len(section.unk2)//16
        
        self.ib = SkeletalIndexBuffer.read(f, name='IB')

        num=read_uint32(f)
        self.active_bone_ids=f.read(num*2)

        read_null(f, 'Parse failed! (LOD:null1)')

        vertex_num=read_uint32(f)

        num=read_uint32(f)
        self.required_bone_ids=f.read(num*2)

        self.vertex_map = read_uint32_array(f)
        self.max_vertex_map_id = read_uint32(f)

        self.uv_num=read_uint32(f)
        self.vb = SkeletalMeshVertexBuffer.read(f, name='VB0')
        check(self.uv_num, self.vb.uv_num)
        self.vb2 = SkinWeightVertexBuffer4.read(f, name='VB2')
        u=read_uint8(f)
        f.seek(-1,1)
        if u==1 and not no_tessellation:#HasVertexColors
            self.color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            self.color_vb=None

        if not no_tessellation:
            self.ib2 = SkeletalIndexBuffer.read(f, name='IB2')
        else:
            self.ib2 = None

        if self.KDI_buffer_size>0:
            self.KDI_buffer=KDIBuffer.read(f, name='KDI_buffer')
            check(self.KDI_buffer.size, self.KDI_buffer_size, f)
            self.KDI_VB=KDIBuffer.read(f, name='KDI_VB')
    
    def write(f, lod):
        write_uint8(f, 1)
        write_uint8(f, lod.ib2 is None)
        write_array(f, lod.sections, SkeletalLODSection.write, with_length=True)
        SkeletalIndexBuffer.write(f, lod.ib)
        write_uint32(f, len(lod.active_bone_ids)//2)
        f.write(lod.active_bone_ids)
        write_null(f)
        write_uint32(f, lod.vb.vertex_num)
        write_uint32(f, len(lod.required_bone_ids)//2)
        f.write(lod.required_bone_ids)
        
        write_uint32_array(f, lod.vertex_map, with_length=True)
        write_uint32(f, lod.max_vertex_map_id)

        write_uint32(f, lod.uv_num)
        SkeletalMeshVertexBuffer.write(f, lod.vb)
        SkinWeightVertexBuffer4.write(f, lod.vb2)

        if lod.color_vb is not None:
            ColorVertexBuffer.write(f, lod.color_vb)

        if lod.ib2 is not None:
            SkeletalIndexBuffer.write(f, lod.ib2)

        if lod.KDI_buffer_size>0:
            KDIBuffer.write(f, lod.KDI_buffer)
            KDIBuffer.write(f, lod.KDI_VB)

    def remove_KDI(self):
        self.KDI_buffer_size=0
        self.KDI_buffer=None
        self.KDI_VB=None
        for section in self.sections:
            section.remove_KDI()

    def parse_buffers_for_blender(self):
        normal, pos, texcoords = self.vb.parse()
        joint, weight = self.vb2.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]
        vertex_groups = [section.vertex_group for section in self.sections]

        ls = [normal, pos, joint, weight]
        normals, positions, joints, weights = [split_list(l, first_vertex_ids) for l in ls]

        texcoords = [split_list(l, first_vertex_ids) for l in texcoords]

        #joints = [[[j_ for j_,w_ in zip(j, w) if w_!=0] for j, w in zip(joint, weight)] for joint, weight in zip(joints, weights)]
        #weights = [[[w_/255 for w_ in w] for w in weight] for weight in weights]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i-first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        return normals, positions, texcoords, vertex_groups, joints, weights, indices

    def import_from_blender(self, primitives):
        s_num1=len(self.sections)
        f_num1=self.ib.size//3
        v_num1=self.vb.vertex_num
        uv_num1 = self.uv_num

        bone_ids = [i for i in range(len(primitives['BONES']))]
        bone_ids = struct.pack('<'+'H'*len(bone_ids), *bone_ids)
        self.active_bone_ids = bone_ids
        self.required_bone_ids = bone_ids
        uv_maps = primitives['UV_MAPS'] #(sction count, uv count, vertex count, 2)
        self.uv_num = len(uv_maps)
        positions = primitives['POSITIONS']
        normals = primitives['NORMALS']
        self.vb.import_from_blender(normals, positions, uv_maps, self.uv_num)
        vertex_count = primitives['VERTEX_COUNTS']
        if self.color_vb is not None:
            self.color_vb.update(sum(vertex_count))
        vertex_groups = primitives['VERTEX_GROUPS']
        material_ids = primitives['MATERIAL_IDS']
        joints = primitives['JOINTS']
        weights = primitives['WEIGHTS']
        indices = primitives['INDICES']

        if len(self.sections)<len(material_ids):
            self.sections += [self.sections[-1].copy() for i in range(len(material_ids)-len(self.sections))]
        self.sections=self.sections[:len(material_ids)]

        max_bone_influences = len(joints[0])
        face_count = [len(ids)//3 for ids in indices]
        first_vertex_id = 0
        first_ids =[]
        first_ib_id = 0
        for section, vg, id, vert_num, face_num in zip(self.sections, vertex_groups, material_ids, vertex_count, face_count):
            first_ids.append(first_vertex_id)
            section.import_from_blender(vg, id, first_vertex_id, vert_num, first_ib_id, face_num, max_bone_influences)
            first_vertex_id += vert_num
            first_ib_id += face_num*3

        self.vb2.import_from_blender(joints, weights, max_bone_influences>4)
        self.color_vb=None

        indices = [[i+first_id for i in ids] for ids, first_id in zip(indices, first_ids)]
        indices = flatten(indices)

        self.ib.update(indices, ((self.vb.size>65000)+1)*2)
        self.ib2 = None
        self.remove_KDI()

        s_num2=len(self.sections)
        f_num2=self.ib.size//3
        v_num2=self.vb.vertex_num
        uv_num2 = self.uv_num

        print('Updated LOD0')
        print('  sections: {} -> {}'.format(s_num1, s_num2))
        print('  faces: {} -> {}'.format(f_num1, f_num2))
        print('  vertices: {} -> {}'.format(v_num1, v_num2))
        print('  uv maps: {} -> {}'.format(uv_num1, uv_num2))

class SkeletalLOD5(SkeletalLOD):

    def read(f, version):
        return SkeletalLOD5(f, version)

    def __init__(self, f, version):
        self.offset=f.tell()
        self.version=version
        one = read_uint16(f)
        check(one, 1, f, 'Parse failed! (LOD:one)')
        read_const_uint32(f, 0)
        read_const_uint32(f, 1)
        self.active_bone_ids=read_uint16_array(f)
        self.sections=[SkeletalLODSection5.read(f, self.version) for i in range(read_uint32(f))]
        self.required_bone_ids=read_uint16_array(f)
        buffer_block_size=read_uint32(f)
        buffer_block_start_offset = f.tell()

        check(read_uint16(f), 1)
        self.ib = SkeletalIndexBuffer.read(f, name='IB')
        self.vb = PositionVertexBuffer.read(f, name='Position_VB')
        check(read_uint16(f), 1)
        self.uv_num = read_uint32(f)
        vertex_num=read_uint32(f)
        use_float32UV = read_uint32(f)
        read_null(f) #use high precision tangent basis?

        self.normal_vb = NormalVertexBuffer.read(f, name='Normal_VB')
        self.uv_vb = UVVertexBuffer.read(f, self.uv_num, use_float32UV, name='UV_VB')

        self.weight_vb = SkinWeightVertexBuffer5.read(f, name='Weight_VB')
        check(read_uint16(f), 1)
        read_null(f)
        read_const_uint32(f, 4)
        if version>='5.0':
            read_null_array(f, 4)
        else:
            read_null(f)
            self.adjacency_vb = SkeletalIndexBuffer.read(f, name='Adjacency_VB')
            read_null(f)
            read_null(f)
        check(f.tell()-buffer_block_start_offset, buffer_block_size)

    def write(f, lod):
        write_uint16(f, 1)
        write_uint32(f, 0)
        write_uint32(f, 1)
        write_uint16_array(f, lod.active_bone_ids, with_length=True)
        write_array(f, lod.sections, SkeletalLODSection5.write, with_length=True)
        write_uint16_array(f, lod.required_bone_ids, with_length=True)
        f.seek(4,1)
        buffer_block_start_offset = f.tell()
        write_uint16(f, 1)
        SkeletalIndexBuffer.write(f, lod.ib)
        PositionVertexBuffer.write(f, lod.vb)

        write_uint16(f, 1)
        write_uint32(f, lod.uv_vb.uv_num)
        write_uint32(f, lod.vb.vertex_num)
        write_uint32(f, lod.uv_vb.use_float32UV)
        write_null(f)
        NormalVertexBuffer.write(f, lod.normal_vb)
        UVVertexBuffer.write(f, lod.uv_vb)
        SkinWeightVertexBuffer5.write(f, lod.weight_vb)
        write_uint16(f, 1)
        write_null(f)
        write_uint32(f, 4)
        if lod.version>='5.0':
            write_null_array(f, 4)
        else:
            write_null(f)
            SkeletalIndexBuffer.write(f, lod.adjacency_vb)
            write_null(f)
            write_null(f)

        end_offset = f.tell()
        buffer_block_size = end_offset - buffer_block_start_offset
        f.seek(buffer_block_start_offset-4)
        write_uint32(f, buffer_block_size)
        f.seek(end_offset)

    def get_buffers(self):
        buffers = [self.ib, self.vb, self.normal_vb, self.uv_vb, self.weight_vb]
        return buffers

    def parse_buffers_for_blender(self):
        normal = self.normal_vb.parse()
        pos = self.vb.parse()
        texcoords = self.uv_vb.parse()
        
        joint, weight = self.weight_vb.parse()
        first_vertex_ids = [section.first_vertex_id for section in self.sections]
        vertex_groups = [section.vertex_group for section in self.sections]

        ls = [normal, pos, joint, weight]
        normals, positions, joints, weights = [split_list(l, first_vertex_ids) for l in ls]
        texcoords = [split_list(l, first_vertex_ids) for l in texcoords]

        #joints = [[[j_ for j_,w_ in zip(j, w) if w_!=0] for j, w in zip(joint, weight)] for joint, weight in zip(joints, weights)]
        #weights = [[[w_/255 for w_ in w] for w in weight] for weight in weights]

        indices = self.ib.parse()
        first_ib_ids = [section.first_ib_id for section in self.sections]
        indices = split_list(indices, first_ib_ids)
        indices = [[i-first_id for i in ids] for ids, first_id in zip(indices, first_vertex_ids)]
        return normals, positions, texcoords, vertex_groups, joints, weights, indices
