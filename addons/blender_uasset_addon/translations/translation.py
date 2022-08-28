"""Translation data.

Notes:
    You can easily add translation data for your language.
    Make a json file like this.

    {
        "language": "your_language",
        "file_name1.py": {
            "eng text 1": "translated text 1",
            "eng text 2": "translated text 2"
        },
        "file_name2.py": {
            "eng text 3": "translated text 2",
            "eng text 4": "translated text 4"
        }
    }

  Then put it in blender_uasset_addon/translations/
  See blender_uasset_addon/translations/Japanese.json for an example
"""
import json
import os

import bpy


def load_json(file):
    """Load a json file."""
    with open(file, 'r', encoding='utf-8') as f:
        j = json.load(f)
    return j


def get_translation():
    """Get translation data."""
    translation_folder = os.path.dirname(__file__)
    trans_dict = {}

    # read json files
    for file in os.listdir(translation_folder):
        if file[-5:] != '.json' or os.path.isdir(file):
            continue
        file_path = os.path.join(translation_folder, file)
        try:
            trans_json = load_json(file_path)
            lang = trans_json.get("language", None)
            if lang is None:
                continue
            lang_dict = {}
            for key, val in trans_json.items():
                if key[-3:] != '.py':
                    continue
                val = {("*", eng): translated for eng, translated in val.items()}
                lang_dict = {**lang_dict, **val}
            trans_dict[lang] = lang_dict
        except Exception as exc:
            print(f'BlenderUassetAddon: translator.py: Failed to read translation data. ({file_path}, {exc})')
    return trans_dict


def register():
    """Add translation data."""
    translations_dict = get_translation()
    bpy.app.translations.register("blender_uasset_addon", translations_dict)


def unregister():
    """Remove translation data."""
    bpy.app.translations.unregister("blender_uasset_addon")
