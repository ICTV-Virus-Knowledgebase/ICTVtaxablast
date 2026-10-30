#!/usr/bin/env bash
#
# tag and push our latest image to docker hub
#

# get docker user from docker login info
echo "RUNNING docker info | grep Username"
EXPECTED_USER="ictvglobal"
DOCKER_USER=$(sudo docker info 2> /dev/null | awk '/Username:/{print $2}')
if [ -z "$DOCKER_USER" ]; then
	echo "ERROR: could not recover Username: from 'sudo docker info'"
	exit 1
fi
if [ "$DOCKER_USER" != "$EXPECTED_USER" ]; then
	echo "ERROR: expected docker user '$EXPECTED_USER' is not logged in; instead '$DOCKER_USER' is currently logged in"
	exit 1
fi
echo DOCKER_USER=$DOCKER_USER
echo ""

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
# tag
# 
echo "RUNNING (local tagging):"
echo sudo docker tag ${DOCKER_CONTAINER_NAME} ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:$VER_STR
     sudo docker tag ${DOCKER_CONTAINER_NAME} ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:$VER_STR
 
echo sudo docker tag ${DOCKER_CONTAINER_NAME} ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:latest
     sudo docker tag ${DOCKER_CONTAINER_NAME} ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:latest

echo ""
echo "SUGGEST (local tagging):"
echo sudo docker tag ${DOCKER_CONTAINER_NAME} ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:prod

#
# tag
#
echo ""
echo "SUGGEST (push to docker hub):"
echo sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:$VER_STR
#    sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:$VER_STR
echo sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:latest
#    sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:latest
echo sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:prod
#    sudo docker push ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:prod

#
# to pull instructions
#
echo ""
echo "# to pull, run (on app.ictv.global, for example):"
echo "docker pull ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:$VER_STR"
echo "docker pull ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:latest"
echo "docker pull ${DOCKER_USER}/${DOCKER_CONTAINER_NAME}:prod"
