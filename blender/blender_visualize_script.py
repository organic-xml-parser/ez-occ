"""
README: This script needs to be run inside blender. Launch blender, navigate to "scripting", and paste this script.
The script allows you to import multiple numbered STL files and keyframe one to each frame of the animation. This way
you can create animations showing evolution e.g. of parametric input values.
"""


import bpy
import os

base_path = "PATH TO IMPORT FROM"

print()

parent = bpy.data.objects.new("imported_stls", None)
bpy.context.scene.collection.objects.link(parent)
parent.empty_display_size = 2
parent.empty_display_type = 'PLAIN_AXES'

stl_material = bpy.data.materials.new(name="STLMaterial")


def sort_key(file_path):
    file_name = os.path.basename(file_path)
    return int(file_name.split("-")[0])


paths = sorted([p for p in os.listdir(base_path) if p.endswith('stl')], key=sort_key)

for i, path in enumerate(paths):
    path = os.path.join(base_path, path)

    if path.endswith('stl'):
        mesh = bpy.ops.import_mesh.stl(filepath=os.path.abspath(path))
        mesh_obj = bpy.context.object
        mesh_obj.parent = parent
        mesh_obj.data.materials.append(stl_material)

        bpy.context.object.hide_render = True
        mesh_obj.keyframe_insert(data_path="hide_render", frame=i - 1)

        bpy.context.object.hide_render = False
        mesh_obj.keyframe_insert(data_path="hide_render", frame=i)

        bpy.context.object.hide_render = True
        mesh_obj.keyframe_insert(data_path="hide_render", frame=i + 1)

bpy.context.scene.frame_end = len(paths) - 1
