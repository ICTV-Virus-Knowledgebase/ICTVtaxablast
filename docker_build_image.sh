#!/usr/bin/env bash
#
# Build directory into docker image
#
#
# First time I ran this on my mac, it failed with
#     => ERROR [internal] load metadata for docker.io/library/ubuntu:22.04
#     ------
#     > [internal] load metadata for docker.io/library/ubuntu:22.04:
#     ------
#     failed to solve with frontend dockerfile.v0: failed to create LLB definition: rpc error: code = Unknown desc = error getting credentials - err: exit status 1, out: ``
# which was fixed via
#    docker pull ubuntu:22.04
#


# add git hash to version
./version_git.sh
VER_FILE=version_git.txt
if [ ! -e "$VER_FILE" ]; then 
	echo ERROR: $VER_FILE not found
	exit 1
fi
VER=$(cat $VER_FILE)

#
# copy in data files
#
# 20260210 curtish now downloading files and building db locally on test
#./pull_blast_from_cheaha.sh

#
# Build image from Dockerfile
#

sudo docker build -t ictv_taxablast .


