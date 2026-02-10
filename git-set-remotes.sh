#!/usr/bin/env bash
#
# set up per-user remotes for github
#

# scan ~/.ssh for *.pub to find users list
# (all keys must be named USER.*.pub)
GIT_USERS=
for KEY_FILE in $(ls ~/.ssh/*.pub); do
	echo "# Found $KEY_FILE"
	GIT_USERS="$GIT_USERS $(basename $KEY_FILE | cut -d . -f 1)"
done

if [[ -z "$GIT_USERS" ]]; then
	echo "ERROR: no ~/.ssh/USER.*.pub ssh keys found"
	exit 1
else
	echo "GIT_USERS=$GIT_USERS"
fi

# 
# create an origin for each user, using "origin" as model
#
ORIGIN_REPO_PATH=$(git remote -v | egrep "origin.*git@github.com.*fetch" | awk '{print $2}' | cut -d : -f 2)

if [[ -z "$ORIGIN_REPO_PATH" ]]; then
	echo "ERROR: git remote found for origin for fetch using git@github.com"
	echo "# git remote -v"
	git remote -v
	exit 1
else
	echo "# ORIGIN_REPO_PATH=$ORIGIN_REPO_PATH"
fi

#
# for each user, create the remote, if it doesn't exist
#
for GIT_USER in $GIT_USERS; do 
	USER_REMOTE_URL="git@github-${GIT_USER}:$ORIGIN_REPO_PATH"
	echo USER_REMOTE_URL=$USER_REMOTE_URL
	grep "$USER_REMOTE_URL" <(git remote -v) > /dev/null
	if [[ $? -eq 0 ]]; then
		echo "# SKIP: remote already exists"
	else
		echo "# ADDING REMOTE "
		echo "git remote add $GIT_USER $USER_REMOTE_URL"
		git remote add $GIT_USER $USER_REMOTE_URL
	fi
done

cat <<EOT
#
# convenience functions for ~/.bashrc
#
EOT

for GIT_USER in $GIT_USERS; do 

	# check if function exists
	egrep "^gitpush-$GIT_USER" ~/.bashrc > /dev/null
	if [[ $? -eq 0 ]]; then
		echo "# SKIP: gitpush-${GIT_USER} already defined in ~/.bashrc"
	else
		echo "# Adding function to ~/.bashrc for $GIT_USER"
		read -p "ENTER user.name for $GIT_USER: " USERNAME
		cat >> ~/.bashrc <<EOT

# mult-person, one user git convenience function
gitpush-${GIT_USER} () {
	local branch="\${1:-main}"
	git config user.name "${USERNAME}"
	git config user.email "${GIT_USER}@uab.edu"
	git push ${GIT_USER} "\$branch"
} 
EOT
	fi
done
