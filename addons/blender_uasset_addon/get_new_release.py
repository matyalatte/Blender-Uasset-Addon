"""UI panel to check and open release page."""
import bpy
import requests

response = requests.get("https://api.github.com/repos/matyalatte/Blender-Uasset-Addon/releases/latest")
if response:
    tag = response.json()['tag_name']
    latest_version = tag[1:].split('.')
    is_valid_tag = (tag[0] == 'v') and (len(latest_version) == 3)
    if not is_valid_tag:
        print(f'get_new_release.py: Got the latest release page. But the tag is invalid. ({tag})')
    title = response.json()['name']
    body = response.json()['body'].split('\n')
else:
    print('get_new_release.py: Failed to get response from the github page.')
    latest_version = []
    is_valid_tag = False
    title = ""
    body = []

class UASSET_PT_get_new_release(bpy.types.Panel):
    """UI panel to open URLs."""
    bl_label = "There is a new release!"
    bl_idname = "UASSET_PT_get_new_release"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = 'Uasset'
    bl_options = {'DEFAULT_CLOSED'}

    urls = {
        'Get the latest version!': 'https://github.com/matyalatte/Blender-Uasset-Addon/releases/latest'
    }
    icons = ['URL']

    def draw(self, context):
        """Draw UI panel to open URLs."""
        layout = self.layout
        col = layout.column()
        for (name, url), icon in zip(UASSET_PT_get_new_release.urls.items(), UASSET_PT_get_new_release.icons):
            ope = col.operator('wm.url_open', text=name, icon=icon)
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
    """Regist UI panel."""
    current_version = [str(v) for v in version]
    if current_version != latest_version and is_valid_tag:
        for cls in classes:
            bpy.utils.register_class(cls)


def unregister(version):
    """Unregist UI panel."""
    if list(version) != latest_version and is_valid_tag:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
