"""
README: This script needs to be run inside blender. Launch blender, navigate to "scripting", and paste this script.

Use SessionUtils.save_stls and SessionUtils.save_keyframes to save keyframe data to an empty directory
Then change BASE_PATH to the absolute path of the dir you wish to import from in your scene and run the script.

Meshes will be imported, named, and keyframed for each frame that you have exported. Note that interpolation is
still pretty janky, so you probably want to export every keyframe you intend to animate.
"""


import bpy
import os
import json
import pdb
import math
import logging
import sys

import logging

logger = logging.getLogger(__name__)


logging.basicConfig(level=logging.INFO)


def get_dir_arg(argv):
    err_msg = "Please provide the absolute path to the directory containing output files"
    if "--" not in argv:
        logger.error(err_msg)
        raise ValueError(err_msg)

    path_index = argv.index("--") + 1

    if path_index >= len(argv):
        logger.error(err_msg)
        raise ValueError(err_msg)

    path = argv[path_index]

    if not os.path.isabs(path):
        err_msg = "Path is not absolute! " + err_msg
        logger.error(err_msg)
        raise ValueError(err_msg)

    return path

base_path = get_dir_arg(sys.argv)


parent = bpy.data.objects.new("imported_stls", None)
bpy.context.scene.collection.objects.link(parent)
parent.empty_display_size = 2
parent.empty_display_type = 'PLAIN_AXES'

stl_material = bpy.data.materials.new(name="STLMaterial")


model_files = {f for f in os.listdir(base_path) if f.endswith(".stl")}


keyframe_files = {f for f in os.listdir(base_path) if f.endswith(".json")}

for f in model_files:
    path = os.path.join(base_path, f)

    model_name = f[:-4]
    if model_name not in bpy.data.objects:
        mesh = bpy.ops.import_mesh.stl(filepath=os.path.abspath(path))
        mesh_obj = bpy.context.object
        mesh_obj.parent = parent
        mesh_obj.data.materials.append(stl_material)

        logger.info("Imported: f{mesh_obj.name}")



for f in keyframe_files:
    with open(os.path.join(base_path, f)) as ff:
        json_doc = json.loads(ff.read())

    keyframe = int(json_doc['keyframe'])
    for name, transforms in json_doc['transforms'].items():
        logger.info(f"setting keyframe {keyframe}, for object: {name}")

        mesh_obj = bpy.data.objects[name]
        mesh_obj.location.x = 0
        mesh_obj.location.y = 0
        mesh_obj.location.z = 0

        mesh_obj.rotation_euler.x = 0
        mesh_obj.rotation_euler.y = 0
        mesh_obj.rotation_euler.z = 0

        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)

        for transform in transforms:
            x = float(transform["x"])
            y = float(transform["y"])
            z = float(transform["z"])

            if transform["type"] == "translation":
                bpy.ops.transform.translate(value=(x, y, z))
            elif transform["type"] == "rotation":
                ov = bpy.context.copy()
                ov['area'] = [a for a in bpy.context.screen.areas if a.type == "VIEW_3D"][0]
                # see https://stackoverflow.com/questions/67659621/how-to-use-the-rotate-operator-on-blender-python-if-you-execute-the-script-on-th
                bpy.ops.transform.rotate(ov,
                    value=x, orient_axis='X',
                    center_override=(0, 0, 0),
                    orient_type='GLOBAL')
                bpy.ops.transform.rotate(ov,
                    value=y, orient_axis='Y',
                    center_override=(0, 0, 0),
                    orient_type='GLOBAL')
                bpy.ops.transform.rotate(ov,
                    value=z, orient_axis='Z',
                    center_override=(0, 0, 0),
                    orient_type='GLOBAL')

        mesh_obj.keyframe_insert(data_path="location", frame=keyframe)
        mesh_obj.keyframe_insert(data_path="rotation_euler", frame=keyframe)