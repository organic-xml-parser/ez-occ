#!/usr/bin/env bash

cp ../requirements.txt ./requirements.txt

docker build . -t ezocc-img:latest
