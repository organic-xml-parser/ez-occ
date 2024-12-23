#!/usr/bin/env bash

# see https://stackoverflow.com/questions/59895/how-do-i-get-the-directory-where-a-bash-script-is-located-from-within-the-script

if [[ ! -d $1 ]]; then
  echo "First argument must be a path to a directory containing the files to be imported into blender"
  exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

DIRECTORY_PATH=$(realpath "$1")

echo "directory path is: $DIRECTORY_PATH"

blender --python "$SCRIPT_DIR"/blender_visualize_script.py -- "$DIRECTORY_PATH"