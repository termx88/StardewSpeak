"""
cxfreeze command line tool
"""

import argparse
import subprocess
import os
import json
import io
import zipfile
import shutil
import sys

import lark
import cx_Freeze
from cx_Freeze.common import normalize_to_list

__all__ = ["main"]

EXCLUDES = ['tkinter']

MAIN = os.path.join('speech-client', 'main.py')

DIST_FOLDER = 'dist'
WSR_SRC_FOLDER = os.path.join('engines', 'RecognizerIO', 'RecognizerIO', 'bin', 'Debug')
WSR_DEST_FOLDER = os.path.join(DIST_FOLDER, 'engines', 'wsr')


DESCRIPTION = """
Freeze a Python script and all of its referenced modules to a base \
executable which can then be distributed without requiring a Python \
installation.
"""

VERSION = """
%(prog)s {}
Copyright (c) 2007-2020 Anthony Tuininga. All rights reserved.
Copyright (c) 2001-2006 Computronix Corporation. All rights reserved.
""".format(
    cx_Freeze.__version__
)

def try_remove_directory(path):
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass

def prepare_parser():
    parser = argparse.ArgumentParser(epilog=VERSION)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--command-folders", nargs="*", metavar="SCRIPT", help="Command module folders")
    parser.add_argument(
        "-O",
        action="count",
        default=0,
        dest="optimize_flag",
        help="optimize generated bytecode as per PYTHONOPTIMIZE; "
        "use -OO in order to remove doc strings",
    )
    parser.add_argument(
        "-c",
        "--compress",
        action="store_true",
        dest="compress",
        help="compress byte code in zip files",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        dest="silent",
        help="suppress all output except warnings and errors",
    )
    parser.add_argument(
        "--command_dir",
        dest="base_name",
        metavar="NAME",
        help="command directory",
    )
    parser.add_argument(
        "--base-name",
        dest="base_name",
        metavar="NAME",
        help="file on which to base the target file; if the name of the file "
        "is not an absolute file name, the subdirectory bases (rooted in the "
        "directory in which the freezer is found) will be searched for a file "
        "matching the name",
    )
    parser.add_argument(
        "--init-script",
        dest="init_script",
        metavar="NAME",
        help="script which will be executed upon startup; if the name of the "
        "file is not an absolute file name, the subdirectory initscripts "
        "(rooted in the directory in which the cx_Freeze package is found) "
        "will be searched for a file matching the name",
    )
    parser.add_argument(
        "--target-name",
        dest="target_name",
        metavar="NAME",
        help="the name of the file to create instead of the base name "
        "of the script and the extension of the base binary",
    )
    parser.add_argument(
        "--default-path",
        action="append",
        dest="default_path",
        metavar="DIRS",
        help="list of paths separated by the standard path separator for the "
        "platform which will be used to initialize sys.path prior to running "
        "the module finder",
    )
    parser.add_argument(
        "--include-path",
        action="append",
        dest="include_path",
        metavar="DIRS",
        help="list of paths separated by the standard path separator for the "
        "platform which will be used to modify sys.path prior to running the "
        "module finder",
    )
    parser.add_argument(
        "--replace-paths",
        dest="replace_paths",
        metavar="DIRECTIVES",
        help="replace all the paths in modules found in the given paths with "
        "the given replacement string; multiple values are separated by the "
        "standard path separator and each value is of the form "
        "path=replacement_string; path can be * which means all paths not "
        "already specified",
    )
    parser.add_argument(
        "--includes",
        "--include-modules",
        dest="includes",
        metavar="NAMES",
        help="comma separated list of modules to include",
    )
    parser.add_argument(
        "--excludes",
        "--exclude-modules",
        dest="excludes",
        metavar="NAMES",
        help="comma separated list of modules to exclude",
    )
    parser.add_argument(
        "--packages",
        dest="packages",
        metavar="NAMES",
        help="comma separated list of packages to include, which includes all "
        "submodules in the package",
    )
    parser.add_argument(
        "--include-files",
        dest="include_files",
        metavar="NAMES",
        help="comma separated list of paths to include",
    )
    parser.add_argument(
        "-z",
        "--zip-include",
        dest="zip_includes",
        action="append",
        default=[],
        metavar="SPEC",
        help="name of file to add to the zip file or a specification of the "
        "form name=arcname which will specify the archive name to use; "
        "multiple --zip-include arguments can be used",
    )
    parser.add_argument(
        "--zip-include-packages",
        dest="zip_include_packages",
        metavar="NAMES",
        help="comma separated list of packages which should be included in "
        "the zip file; the default is for all packages to be placed in the "
        "file system, not the zip file; those packages which are known to "
        "work well inside a zip file can be included if desired; use * to "
        "specify that all packages should be included in the zip file",
    )
    parser.add_argument(
        "--zip-exclude-packages",
        dest="zip_exclude_packages",
        default="*",
        metavar="NAMES",
        help="comma separated list of packages which should be excluded from "
        "the zip file and placed in the file system instead; the default is "
        "for all packages to be placed in the file system since a number of pa"
        "ckages assume that is where they are found and will fail when placed "
        "in a zip file; use * to specify that all packages should be placed "
        "in the file system and excluded from the zip file (the default)",
    )
    parser.add_argument(
        "--icon", dest="icon", help="name of the icon file for the application"
    )
    # remove the initial "usage: " of format_usage()
    parser.usage = parser.format_usage()[len("usage: ") :] + DESCRIPTION
    return parser


def parse_command_line(parser):
    args = parser.parse_args()
    args.excludes = normalize_to_list(args.excludes)
    args.includes = normalize_to_list(args.includes)
    args.packages = normalize_to_list(args.packages)
    args.zip_include_packages = normalize_to_list(args.zip_include_packages)
    args.zip_exclude_packages = normalize_to_list(args.zip_exclude_packages)
    replace_paths = []
    if args.default_path is not None:
        sys.path = [p for mp in args.default_path for p in mp.split(os.pathsep)]
    if args.include_path is not None:
        paths = [p for mp in args.include_path for p in mp.split(os.pathsep)]
        sys.path = paths + sys.path
    sys.path.insert(0, os.path.dirname(MAIN))
    args.include_files = normalize_to_list(args.include_files)
    zip_includes = []
    if args.zip_includes:
        for spec in args.zip_includes:
            if "=" in spec:
                zip_includes.append(spec.split("=", 1))
            else:
                zip_includes.append(spec)
    args.zip_includes = zip_includes
    return args

def zipdir(path):
    # ziph is zipfile handle
    file_like_object = io.BytesIO()
    zipfile_ob = zipfile.ZipFile(file_like_object, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9)
    for root, dirs, files in os.walk(path):
        for file in files:
            zipfile_ob.write(os.path.join(root, file))
    return file_like_object

def copy_dir(root_src_dir, root_dst_dir, filter=None):
    try_remove_directory(root_dst_dir)
    for src_dir, dirs, files in os.walk(root_src_dir):
        files_to_write = [f for f in files if filter(f)] if filter else files
        if files_to_write:
            dst_dir = src_dir.replace(root_src_dir, root_dst_dir, 1)
            os.makedirs(dst_dir, exists_ok=True)
            for file_ in files_to_write:
                src_file = os.path.join(src_dir, file_)
                dst_file = os.path.join(dst_dir, file_)
                shutil.copy(src_file, dst_dir)

def filter_commands():
    pass

def build_release():
    msbuild = r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe"
    sln = os.path.abspath(os.path.join('..', '..', '..', 'StardewSpeak.sln'))
    subprocess.run([msbuild, sln, '/p:Configuration=Release', "/t:Clean;Rebuild"])

def main():
    args = parse_command_line(prepare_parser())
    app_name = 'speech-client'
    app_root = os.path.join('dist')
    try_remove_directory(app_root)
    executables = [
        cx_Freeze.Executable(
            MAIN,
            args.init_script,
            args.base_name,
            app_name,
            args.icon,
        )
    ]
    
    freezer = cx_Freeze.Freezer(
        executables,
        includes=["codecs"],
        excludes=EXCLUDES,
        packages=args.packages,
        compress=args.compress,
        optimizeFlag=args.optimize_flag,
        path=None,
        targetDir=app_root,
        includeFiles=[('Lib\site-packages\webrtcvad_wheels-2.0.10.post2.dist-info', 'lib\webrtcvad_wheels-2.0.10.post2.dist-info')],
        zipIncludes=args.zip_includes,
        silent=args.silent,
        zipIncludePackages=args.zip_include_packages,
        zipExcludePackages=args.zip_exclude_packages,
    )
    freezer.Freeze()
    build_release()


if __name__ == "__main__":
    main()