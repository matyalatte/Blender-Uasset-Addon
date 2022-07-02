# Tools for development

## Python Scripts
There are some python scripts to test the addon.

- `regist_without_installing.py`: Script to use the addon without installing it in Blender.
- `test.py`: Script to check if the addon can reconstract .uasset files.

## flake8
[flake8](https://github.com/pycqa/flake8) is a tool for style guide enforcement.<br>
It will check if you are following [PEP8](https://peps.python.org/pep-0008/).<br>
Install it with `pip install flake8`.<br>
Then, type `flake8` in the same directory as `blender_uasset_addon` and `setup.cfg`.<br>
You should get no messages from flake8.
