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

#
# target docker container naem
#
NAME_FILE=docker_container_name.txt
if [ ! -e "$NAME_FILE" ]; then 
	echo "ERROR: $NAME_FILE not found"
	exit 1
fi
echo READING $NAME_FILE
DOCKER_CONTAINER_NAME=$(egrep -v "^#" $NAME_FILE| sed 's/[ \t\r\n]*//g')
echo DOCKER_CONTAINER_NAME=$DOCKER_CONTAINER_NAME
echo ""

# get version+git_hash
echo RUNNING ./version_git.sh
./version_git.sh
VER_FILE=version_git.txt
if [ ! -e "$VER_FILE" ]; then 
	echo "ERROR: $VER_FILE not found"
	exit 1
fi
echo READING $VER_FILE
VER_STR=$(egrep -v "^#" $VER_FILE)
echo VER_STR=$VER_STR
echo ""


#
# copy in data files
#
# 20260210 curtish now downloading files and building db locally on test
#./pull_blast_from_cheaha.sh

#
# Build image from Dockerfile
#

sudo docker build -t $DOCKER_CONTAINER_NAME .


