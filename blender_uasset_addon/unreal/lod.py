from ..util.io_util import *
from ..util.logger import logger

from .lod_section import StaticLODSection, SkeletalLODSection
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
            if lod.color_vb is None:
                logger.warn('The original mesh has color VB. But your mesh doesn\'t. I don\'t know if the injection works.')
        self.uv_num = lod.uv_num
        logger.log('LOD{} has been imported.'.format(name))
        logger.log('  faces: {} -> {}'.format(f_num1, f_num2))
        logger.log('  vertices: {} -> {}'.format(v_num1, v_num2))
        logger.log('  uv maps: {} -> {}'.format(uv_num1, uv_num2))

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
    def __init__(self, offset, sections, flags, vb, vb2, color_vb, ib, ib2, unk):
        self.offset = offset
        self.sections = sections
        self.flags = flags
        self.uv_num = vb2.uv_num
        super().__init__(vb, vb2, ib, ib2, color_vb=color_vb)
        self.unk = unk
        self.face_num=0
        for section in self.sections:
            self.face_num+=section.face_num

    def read(f):
        offset = f.tell()
        one = read_uint16(f) #strip flags
        check(one, 1, f)
        sections = read_array(f, StaticLODSection.read)

        flags = f.read(4)

        vb = PositionVertexBuffer.read(f, name='VB0') #xyz
        vb2 = StaticMeshVertexBuffer.read(f, name='VB2') #normals+uv_maps

        one = read_uint32(f)
        if one!=1: #color vertex buffer
            f.seek(-4, 1)
            color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            color_vb = None
            null=f.read(6)
            check(null, b'\x00'*6, f)

        ib = StaticIndexBuffer.read(f, name='IB')
        read_null(f)
        read_const_uint32(f, 1)
        null = read_uint32(f)
        if null!=0:
            raise RuntimeError('Unsupported index buffer detected. You can not import "Adjacency Buffer" and "Reversed Index Buffer".')

        ib2 = StaticIndexBuffer.read(f, name='IB2')
        unk = f.read(48)
        return StaticLOD(offset, sections, flags, vb, vb2, color_vb, ib, ib2, unk)

    def write(f, lod):
        write_uint16(f, 1)
        write_array(f, lod.sections, StaticLODSection.write, with_length=True)
        f.write(lod.flags)
        PositionVertexBuffer.write(f, lod.vb)
        StaticMeshVertexBuffer.write(f, lod.vb2)

        if lod.color_vb is not None:
            ColorVertexBuffer.write(f, lod.color_vb)
        else:
            write_uint32(f, 1)
            f.write(b'\x00'*6)

        StaticIndexBuffer.write(f, lod.ib)
        write_uint32_array(f, [0, 1, 0])
        StaticIndexBuffer.write(f, lod.ib2)
        f.write(lod.unk)

    def print(self, i, padding=0):
        pad=' '*padding
        logger.log(pad+'LOD{} (offset: {})'.format(i, self.offset))
        for j in range(len(self.sections)):
            self.sections[j].print(j, padding=padding+2)
        logger.log(pad+'  face_num: {}'.format(self.face_num))
        logger.log(pad+'  vertex_num: {}'.format(self.vb.vertex_num))
        logger.log(pad+'  uv_num: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            buf.print(padding=padding+2)

    def import_LOD(self, lod, name=''):
        super().import_LOD(lod, name=name)
        if len(self.sections)<len(lod.sections):
            self.sections += [self.sections[-1].copy() for i in range(len(lod.sections)-len(self.sections))]
        self.sections=self.sections[:len(lod.sections)]
        for self_section, lod_section in zip(self.sections, lod.sections):
            self_section.import_section(lod_section)
        self.face_num = lod.face_num
        self.flags = lod.flags
        #self.unk = new_lod.unk #if import this, umodel will crash

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


#LOD for skeletal mesh
class SkeletalLOD(LOD):
    #sections: mesh data is separeted into some sections.
    #              each section has material id and vertex group.
    #active_bone_ids: maybe bone ids. but I don't know how it works.
    #bone_ids: active bone ids?
    #uv_num: the number of uv maps

    def __init__(self, f, ff7r=True):
        self.offset=f.tell()
        one = read_uint8(f)
        check(one, 1, f, 'Parse failed! (LOD:one)')
        self.no_tessellation = read_uint8(f)
        self.sections=[SkeletalLODSection.read(f, ff7r=ff7r) for i in range(read_uint32(f))]

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
        
        i=read_uint32(f)
        if i==0:
            self.null8=True
            read_null(f, 'Parse failed! (LOD:null2)')
        else:
            self.null8=False
            f.seek(-4,1)

        chk=read_uint32(f)
        if chk==vertex_num:
            self.unk_ids=read_uint32_array(f, len=vertex_num+1)
        else:
            self.unk_ids=None
            f.seek(-4,1)

        self.uv_num=read_uint32(f)
        self.vb = SkeletalMeshVertexBuffer.read(f, name='VB0')
        check(self.uv_num, self.vb.uv_num)
        self.vb2 = SkinWeightVertexBuffer.read(f, name='VB2')
        u=read_uint8(f)
        f.seek(-1,1)
        if u==1 and not self.no_tessellation:#HasVertexColors
            self.color_vb = ColorVertexBuffer.read(f, name='ColorVB')
        else:
            self.color_vb=None

        if not self.no_tessellation:
            self.ib2 = SkeletalIndexBuffer.read(f, name='IB2')
        else:
            self.ib2 = None

        if self.KDI_buffer_size>0:
            self.KDI_buffer=KDIBuffer.read(f, name='KDI_buffer')
            check(self.KDI_buffer.size, self.KDI_buffer_size, f)
            self.KDI_VB=KDIBuffer.read(f, name='KDI_VB')

    def read(f, ff7r):
        return SkeletalLOD(f, ff7r=ff7r)
    
    def write(f, lod):
        write_uint8(f, 1)
        write_uint8(f, lod.no_tessellation)
        write_array(f, lod.sections, SkeletalLODSection.write, with_length=True)
        SkeletalIndexBuffer.write(f, lod.ib)
        write_uint32(f, len(lod.active_bone_ids)//2)
        f.write(lod.active_bone_ids)
        write_null(f)
        write_uint32(f, lod.vb.vertex_num)
        write_uint32(f, len(lod.required_bone_ids)//2)
        f.write(lod.required_bone_ids)
        
        if lod.null8:
            write_null(f)
            write_null(f)
        if lod.unk_ids is not None:
            write_uint32(f, lod.vb.vertex_num)
            write_uint32_array(f, lod.unk_ids)
        write_uint32(f, lod.uv_num)
        SkeletalMeshVertexBuffer.write(f, lod.vb)
        SkinWeightVertexBuffer.write(f, lod.vb2)

        if lod.color_vb is not None:
            ColorVertexBuffer.write(f, lod.color_vb)

        if not lod.no_tessellation:
            SkeletalIndexBuffer.write(f, lod.ib2)

        if lod.KDI_buffer_size>0:
            KDIBuffer.write(f, lod.KDI_buffer)
            KDIBuffer.write(f, lod.KDI_VB)

    def import_LOD(self, lod, name=''):
        self.no_tessellation = lod.no_tessellation
        super().import_LOD(lod, name=name)
        if len(self.sections)<len(lod.sections):
            self.sections += [self.sections[-1].copy() for i in range(len(lod.sections)-len(self.sections))]
        self.sections=self.sections[:len(lod.sections)]
        for self_section, lod_section in zip(self.sections, lod.sections):
            self_section.import_section(lod_section)
        
        self.active_bone_ids=lod.active_bone_ids
        self.required_bone_ids=lod.required_bone_ids
        if self.KDI_buffer_size>0:
            if self.vb.vertex_num>=self.KDI_VB.size:
                self.KDI_VB.buf=self.KDI_VB.buf[:self.vb.vertex_num*16]
            else:
                self.KDI_VB.buf=b''.join([self.KDI_VB.buf, b'\xff'*4*(self.vb.vertex_num-self.KDI_VB.size)])
            self.KDI_VB.size=self.vb.size

    def get_buffers(self):
        buffers = super().get_buffers()
        if self.KDI_buffer_size>0:
            buffers += [self.KDI_buffer, self.KDI_VB]
        return buffers

    def print(self, name, bones, padding=0):
        pad=' '*padding
        logger.log(pad+'LOD '+name+' (offset: {})'.format(self.offset))
        for i in range(len(self.sections)):
            self.sections[i].print(str(i),bones, padding=padding+2)
        pad+=' '*2
        logger.log(pad+'  face num: {}'.format(self.ib.size//3))
        logger.log(pad+'  vertex num: {}'.format(self.vb.vertex_num))
        logger.log(pad+'  uv num: {}'.format(self.uv_num))
        for buf in self.get_buffers():
            if buf is not None:
                buf.print(padding=padding+2)

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

    def import_gltf(self, gltf):
        bone_ids = [i for i in range(len(gltf.bones))]
        bone_ids = struct.pack('<'+'H'*len(bone_ids), *bone_ids)
        self.active_bone_ids = bone_ids
        self.required_bone_ids = bone_ids
        self.uv_num = gltf.uv_num
        texcoords = [flatten(l) for l in gltf.texcoords]
        pos_range = self.vb.get_range()
        positions = flatten(gltf.positions)
        x = [pos[0] for pos in positions]
        y = [pos[2] for pos in positions]
        z = [pos[1] for pos in positions]
        pos_range_gltf = [max(x)-min(x), max(y)-min(y), max(z)-min(z)]
        c=0
        for i in range(3):
            c+=pos_range_gltf[i]>(pos_range[i]*10)
        if c>=2:
            positions = [[p/100 for p in pos] for pos in positions]

        self.vb.import_gltf(flatten(gltf.normals), flatten(gltf.tangents), positions, texcoords, gltf.uv_num)

        joints = gltf.joints
        weights = gltf.weights
        joints2 = gltf.joints2
        weights2 = gltf.weights2

        if joints2!=[]:
            joints = [[j+j2 for j,j2 in zip(joint, joint2)] for joint, joint2 in zip(joints, joints2)]
            weights = [[w+w2 for w,w2 in zip(weight, wegiht2)] for weight, wegiht2 in zip(weights, weights2)]
        vertex_groups = [[[m for m,n in zip(j,w) if n>0] for j,w in zip(joint, weight)] for joint, weight in zip(joints, weights)]
        vertex_groups = [list(set(flatten(vg))) for vg in vertex_groups]
        for vg in vertex_groups:
            if len(vg)>255:
                print(len(vg))
                raise RuntimeError('Can not use more than 255 bones for a material.')
        
        if len(self.sections)<len(joints):
            self.sections += [self.sections[-1].copy() for i in range(len(joints)-len(self.sections))]
        self.sections=self.sections[:len(joints)]

        max_bone_influences = 4*(1+(joints2!=[]))
        vertex_nums = [len(joint) for joint in gltf.joints]
        face_nums = [len(face)//3 for face in gltf.indices]
        first_vertex_id = 0
        first_ids =[]
        first_ib_id = 0
        for section, vg, id, vert_num, face_num in zip(self.sections, vertex_groups, gltf.material_ids, vertex_nums, face_nums):
            first_ids.append(first_vertex_id)
            section.import_gltf(vg, id, first_vertex_id, vert_num, first_ib_id, face_num, max_bone_influences)
            first_vertex_id += vert_num
            first_ib_id += face_num*3
        vertex_groups = [vg+[0] for vg in vertex_groups]

        joints = [[[vg.index(m)*(n!=0) for m,n in zip(j,w)] for j, w in zip(joint, weight)] for joint, weight, vg in zip(joints, weights, vertex_groups)]

        self.vb2.import_gltf(flatten(joints), flatten(weights), joints2!=[])
        indices = [[i+first_id for i in ids] for ids, first_id in zip(gltf.indices, first_ids)]
        indices = flatten(indices)
        self.ib.update(indices, ((self.vb.size>65000)+1)*2)
        self.no_tessellation=True
        self.ib2 = None
        #indices = [indices[i*3:(i+1)*3] for i in range(len(indices)//3)]
        #indices = [f + [f[0] + f[1] + f[1] + f[2] + f[2] + f[0]] + f for f in indices]
        #indices = flatten(indices)
        #self.ib2.update(indices, ((self.vb.size>65000)+1)*2)

        self.remove_KDI()
