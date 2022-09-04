"""UI panel and operator to export .uasset files."""

import os
import time
import tempfile
import shutil

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Operator, PropertyGroup

from . import bpy_util
from .util.io_util import make_temp_file
from .texconv.texconv import Texconv
from .unreal.uasset import Uasset
from .unreal.dds import DDS
from .inject_to_uasset import UASSET_OT_select_uasset

fmt_list = [
    'DXT1/BC1',
    'DXT5/BC3',
    'BC4/ATI1',
    'BC5/ATI2',
    'BC6H(unsigned)',
    'BC7',
    'FloatRGBA',
    'B8G8R8A8'
]


def inject_texture(tex, source_file, directory, ue_version='4.18', invert_normals=False, no_err=False, texconv=None,
                   no_mips=False, force_uncompressed=False):
    """Export a texture form .uasset file.

    Args:
        file (string): file path to .uasset file
        invert_normals (bool): Flip y axis if the texture is normal map.
        texconv (Texconv): Texture converter for dds.

    Returns:
        tex (bpy.types.Image): loaded texture
    """
    file_format = tex.file_format
    filepath_raw = tex.filepath_raw

    temp = make_temp_file(suffix='.tga')
    tex.file_format = 'TARGA_RAW'
    tex.filepath_raw = temp
    tex.save()

    if texconv is None:
        texconv = Texconv()
    try:
        asset = Uasset(source_file, version=ue_version, asset_type='Texture')
        utex = asset.uexp.texture
        dds_fmt = utex.format_name
        if force_uncompressed:
            if 'BC1' in dds_fmt or 'BC7' in dds_fmt:
                dds_fmt = 'B8G8R8A8'
            if 'BC6' in dds_fmt:
                dds_fmt = 'FloatRGBA'
            utex.change_format(dds_fmt)
        if len(utex.mipmaps) == 1:
            no_mips = True
        texture_type = utex.uasset.asset_type

        temp_dds = texconv.convert_to_dds(temp, dds_fmt, texture_type=texture_type, out=os.path.dirname(temp),
                                          invert_normals=invert_normals, no_mips=no_mips)
        if temp_dds is None:  # if texconv doesn't exist
            raise RuntimeError('Failed to convert texture.')
        dds = DDS.load(temp_dds)
        utex.inject_dds(dds)
        actual_name = os.path.basename(asset.actual_path)
        asset_path = os.path.join(directory, actual_name)
        asset.save(asset_path)

    except Exception as e:
        if not no_err:
            raise e
        print(f'Failed to load {file}')
        tex = None

    tex.file_format = file_format
    tex.filepath_raw = filepath_raw

    if os.path.exists(temp):
        os.remove(temp)
    if os.path.exists(temp_dds):
        os.remove(temp_dds)
    
    return tex


class UASSET_OT_inject_texture(Operator):
    """Operator to inject texture to .uasset files."""
    bl_idname = 'uasset.inject_texture'
    bl_label = 'Inject to Uasset'
    bl_description = 'Inject textures to .uasset files'
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name="target_dir",
        default=''
    )

    def draw(self, context):
        """Draw options for file picker."""
        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False  # No animation.
        props = ['ue_version', 'source_file']
        general_options = context.scene.uasset_general_options
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        for prop in props:
            col.prop(general_options, prop)
        inject_options = context.scene.uasset_inject_options
        props = ['force_uncompressed', 'no_mips']
        for prop in props:
            col.prop(inject_options, prop)

    def invoke(self, context, event):
        """Invoke."""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        """Run the operator."""
        return self.export_dds(context)

    def export_dds(self, context):
        """Export a file."""
        try:
            start_time = time.time()
            tex = bpy_util.get_texture(context)
            general_options = context.scene.uasset_general_options
            inject_options = context.scene.uasset_inject_options
            inject_texture(tex, general_options.source_file, self.directory,
                     ue_version=general_options.ue_version, force_uncompressed=inject_options.force_uncompressed,
                     no_mips=inject_options.no_mips)

            elapsed_s = f'{(time.time() - start_time):.2f}s'
            m = f'Success! Injected texture to .uasset in {elapsed_s}'
            print(m)
            self.report({'INFO'}, m)
            ret = {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, e.args[0])
            ret = {'CANCELLED'}
        return ret


class UASSET_PT_texture_panel(bpy.types.Panel):
    """UI panel for improt function."""
    bl_label = "Inject to Uasset"
    bl_idname = 'UASSET_PT_texture_panel'
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Uasset"

    def draw(self, context):
        """Draw UI panel."""
        layout = self.layout
        layout.operator(UASSET_OT_inject_texture.bl_idname, icon='TEXTURE_DATA')
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        general_options = context.scene.uasset_general_options
        col.prop(general_options, 'ue_version')
        col.prop(general_options, 'source_file')
        text = bpy_util.translate(UASSET_OT_select_uasset.bl_label)
        layout.operator(UASSET_OT_select_uasset.bl_idname, text=text, icon='FILE')


classes = (
    UASSET_OT_inject_texture,
    UASSET_PT_texture_panel,
)


def register():
    """Add UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    """Remove UI panel, operator, and properties."""
    for c in classes:
        bpy.utils.unregister_class(c)
