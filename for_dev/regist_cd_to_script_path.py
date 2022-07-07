"""Script to regist current dir to script path in preferences.

Notes:
    Run this command before running pytest.
    "%BLENDER_EXE%" --background --python for_dev/regist_cd_to_script_path.py
"""
import bpy
import os

if __name__ == '__main__':
    bpy.context.preferences.filepaths.script_directory = os.getcwd()
    bpy.ops.wm.save_userpref()
