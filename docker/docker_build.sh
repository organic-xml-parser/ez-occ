#!/usr/bin/env bash

pushd ..
docker build . -t ezocc-img:latest -f docker/Dockerfile
popd
