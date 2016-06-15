#!/usr/bin/env bash
cd `dirname $0`/..
ryu-manager ryu.topology.switches topospec.topospec --observe-links \
    --noexplicit-drop --log-config-file=conf/log.ini

