#!/bin/bash
# Generate Python code from proto files

python -m grpc_tools.protoc \
    -I. \
    --python_out=../core \
    --grpc_python_out=../core \
    maven.proto

