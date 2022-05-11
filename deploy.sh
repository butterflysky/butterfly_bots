#!/bin/sh
set -e
set -x

cd  src/adonis_blue
bump2version --verbose --list patch
cd ../..
docker compose build
docker compose up -d
