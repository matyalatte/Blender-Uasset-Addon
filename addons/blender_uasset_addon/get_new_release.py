"""UI panel to check and open release page."""
import requests

import bpy
from . import bpy_util


def get_release_info():
    """Get info from the latest release page."""
    err_tag = "BlenderUassetAddon: get_new_release.py"
    try:
        response = requests.get("https://api.github.com/repos/matyalatte/Blender-Uasset-Addon/releases/latest")
        response.raise_for_status()
        if response:
            response_json = response.json()
            for key in ['tag_name', 'name', 'body']:
                if key not in response_json:
                    raise RuntimeError(f'Got the latest release page. But a key is missing. ({key})')
            tag = response_json['tag_name']
            latest_version = tag[1:].split('.')
            is_valid_tag = (tag[0] == 'v') and (len(latest_version) == 3)
            if not is_valid_tag:
                raise RuntimeError(f'Got the latest release page. But the tag is invalid. ({tag})')
            title = response_json['name']
            body = response_json['body'].split('\n')
        else:
            raise RuntimeError('Failed to get response from the github page.')

    except Exception as ex:
        print(f'{err_tag}: {ex}')
        latest_version = []
        is_valid_tag = False
        title = ""
        body = []
    return latest_version, is_valid_tag, title, body


latest_version, is_valid_tag, title, body = get_release_info()


class UASSET_PT_get_new_release(bpy.types.Panel):
    """UI panel to open URLs."""
    bl_label = "There is a new release!"
    bl_idname = "UASSET_PT_get_new_release"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = 'Uasset'
    bl_options = {'DEFAULT_CLOSED'}

    urls = {
        'Get the latest version!': 'https://github.com/matyalatte/Blender-Uasset-Addon'
    }
    icons = ['URL']

    def draw(self, context):
        """Draw UI panel to open URLs."""
        layout = self.layout
        col = layout.column()
        for (name, url), icon in zip(UASSET_PT_get_new_release.urls.items(), UASSET_PT_get_new_release.icons):
            ope = col.operator('wm.url_open', text=bpy_util.translate(name), icon=icon)
            ope.url = url
        col.label(text=title)
        for line in body:
            if line[-1] == '\r':
                line = line[:-1]
            col.label(text=line)


classes = (
    UASSET_PT_get_new_release,
)


def register(version):
    """Add UI panel."""
    current_version = [str(v) for v in version]
    if current_version != latest_version and is_valid_tag:
        for cls in classes:
            bpy.utils.register_class(cls)


def unregister(version):
    """Remove UI panel."""
    current_version = [str(v) for v in version]
    if current_version != latest_version and is_valid_tag:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
