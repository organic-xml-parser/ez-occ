#!/usr/bin/env bash

docker container rm ezocc-container

vals=($(xauth list $DISPLAY | head -n 1))

XAUTH_ADD_ARG="${vals[1]} ${vals[2]}" docker compose run --name ezocc-container app

