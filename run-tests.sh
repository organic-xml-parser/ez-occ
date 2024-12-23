#!/usr/bin/env bash

./examples/compile_examples.py /wsp/README.md

# add -k flag to filter tests by pattern
pytest tst