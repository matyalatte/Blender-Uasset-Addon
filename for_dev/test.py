"""Script to check if the addon can reconstract files.

Notes:
    Put test.py in the same directory as blender_uasset_addon,
    and run the command below.
    python test.py file --version=version --verbose
"""
if __name__ == "__main__":
    import argparse
    import os
    import shutil
    from blender_uasset_addon import unreal, util

    mkdir = util.io_util.mkdir
    compare = util.io_util.compare

    def get_args():
        """Get arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument('file', help='.uasset')
        parser.add_argument('--version', default='5.0', help='UE version')
        parser.add_argument('--verbose', action='store_true', help='Show logs')
        args = parser.parse_args()
        return args

    args = get_args()
    file = args.file
    verbose = args.verbose
    if file[-4:] == 'uexp':
        file = file[:-4] + 'uasset'
    if file[-5:] == 'ubulk':
        file = file[:-5] + 'uasset'
    version = args.version
    uasset = unreal.uasset.Uasset(file, version=version, verbose=verbose)
    save_folder = '__temp__'
    if os.path.exists(save_folder):
        shutil.rmtree(save_folder)
    mkdir(save_folder)
    base = os.path.basename(file)
    new_file = os.path.join(save_folder, base)
    uasset.save(new_file)
    compare(file[:-6] + 'uexp', new_file[:-6] + 'uexp')
    compare(file, new_file)
