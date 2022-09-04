[![discord](https://badgen.net/badge/icon/discord?icon=discord&label)](https://discord.gg/Qx2Ff3MByF)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![ci](https://github.com/matyalatte/Blender-Uasset-Addon/actions/workflows/ci.yml/badge.svg)
![build](https://github.com/matyalatte/Blender-Uasset-Addon/actions/workflows/build.yml/badge.svg)
![pylint](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/matyalatte/f1a5f45e1346698f50387619ff6c5bf7/raw/blender_uasset_addon_pylint_badge.json)
![coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/matyalatte/0ca588aa8786d78c95ce2acdeb90635c/raw/blender_uasset_addon_pytest_badge.json)

# Blender Uasset Addon v0.2.1
Blender addon to mod .uasset files.


<img src="https://user-images.githubusercontent.com/69258547/176998434-48f409f4-55c6-4100-9e31-e5797f7c79c9.png" width="300">

## Features

- Import assets from .uasset files
- Import mesh assets with textures
- Inject meshes, armatures, and animations to .uasset files

## Supported Versions and Assets

:heavy_check_mark:: Supported<br>
:warning:: Experimental<br>
:x:: Unsupported

| UE version | Skeletal Mesh | Static Mesh | Skeleton | Texture | Animation | Injection |
| :---: |:---:|:---:|:---:|:---:|:---:|:---:|
| FF7R | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :warning: | :heavy_check_mark: |
| KH3 | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :heavy_check_mark: | :warning: | :x: |
| 4.18 | :warning: | :warning: | :heavy_check_mark:  | :heavy_check_mark: | :x: | :warning: |
| 4.26, 4.27| :warning: | :warning: | :heavy_check_mark: | :heavy_check_mark: | :x: | :x: |
| 5.0 | :warning: | :warning: | :heavy_check_mark: | :heavy_check_mark: | :x: | :x: |

## Getting Started
[Getting Started · matyalatte/Blender-Uasset-Addon Wiki](https://github.com/matyalatte/Blender-Uasset-Addon/wiki/Getting-Started)

## FAQ
[FAQ · matyalatte/Blender-Uasset-Addon Wiki](https://github.com/matyalatte/Blender-Uasset-Addon/wiki/FAQ)

## Build with Github Actions
There is a workflow to build a DLL and zip it with python scripts.<br>
[How to Build With Github Actions · matyalatte/Blender-Uasset-Addon Wiki](https://github.com/matyalatte/Blender-Uasset-Addon/wiki/How-to-Build-With-Github-Actions)

## Translation
The addon supports translation system.<br>
You can easily add translation data for your language.<br>
[Add Translation Data · matyalatte/Blender-Uasset-Addon Wiki](https://github.com/matyalatte/Blender-Uasset-Addon/wiki/Add-Translation-Data)