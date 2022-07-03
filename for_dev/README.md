# Tools for development

## Python Scripts
There are some python scripts to test the addon.

- `regist_without_installing.py`: Script to use the addon without installing it in Blender.
- `test.py`: Script to check if the addon can reconstract .uasset files.
- `lint.py`: Script to run pylint

## flake8
[flake8](https://github.com/pycqa/flake8) is a tool for style guide enforcement.<br>
It will check if you are following [PEP8](https://peps.python.org/pep-0008/).<br>
Install it with `pip install flake8`.<br>
Then, type `flake8` in the same directory as `blender_uasset_addon` and `setup.cfg`.<br>
You should get no messages from flake8.

## pydocstyle
[pydocstyle](http://www.pydocstyle.org/en/stable/) is a tool for docsting style enforcement.<br>
It will check if you are following [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) for docstrings.<br>
Install it with `pip install pydocstyle`.<br>
Then, type `pydocstyle` in the same directory as `blender_uasset_addon` and `setup.cfg`.<br>
You should get no messages from pydocstyle.

## pylint
[pylint](https://pylint.pycqa.org/en/latest/) is a static code analyser.<br>
It can rate your scripts.<br>
Install it with `pip install pylint`.<br>
Then, type `python for_dev\lint.py --path=blender_uasset_addon` in the same directory as `blender_uasset_addon` and `setup.cfg`.<br>
You will get results like `PyLint Passed | Score:...`.<br>
The score should be more than 7.<br>