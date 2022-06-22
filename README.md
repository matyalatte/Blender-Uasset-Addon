![packaging](https://github.com/matyalatte/Blender-Uasset-Addon/actions/workflows/main.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Blender Uasset Addon v0.1.4
Blender addon to import .uasset files

Most of the source code is from [my mesh tool](https://github.com/matyalatte/FF7R-mesh-importer) and [texture tool](https://github.com/matyalatte/UE4-DDS-Tools).

:warning: **This addon will only work with FF7R's assets for now.**

## Features

- Import assets from .uasset files
- Inject meshes and armatures to .uasset files

## Supported UE Versions

- FF7R

## Supported Assets

- Skeletal mesh
- Static mesh
- Skeleton (*_Skeleton.uasset)
- Texture (Blender will load assets as dds textures. But I don't know if it supports all dds formats.)

## Installation

1. Update Blender if you are using Blender 2.7x.
1. Download `blender_uasset_addon_*.zip` from [the releases page](https://github.com/matyalatte/Blender-Uasset-Addon/releases).
1. Open Blender.
1. Open the `Preferences` window (Edit > Preferences).
1. Select the `Add-ons` tab.
1. Click `Install...`.
1. Select the zip file you downloaded and click `Install Add-on`.
1. You can select `Uasset (.uasset)` from File > Import.

