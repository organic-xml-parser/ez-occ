#!/usr/bin/env bash

project_file=$1

#shorthand script for creating a new project file
if [[ -e $project_file ]]; then
  echo "Project file already exists"
  exit 1
fi

cp project_template.py $project_file
chmod +x $project_file
