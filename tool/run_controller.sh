#!/usr/bin/env bash
cd `dirname $0`/..
ryu-manager topospec.topospec --config-file=topospec.conf
