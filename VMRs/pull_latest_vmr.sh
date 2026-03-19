#!/usr/bin/env bash
##
## Drupal does an HTTP 307 redirect
## curl doesn't know how to handle those
CURRENT_URL=https://ictv.global/vmr/current
OUT_DIR=./VMRs

mkdir -p $OUT_DIR

echo "# Accessing $CURRENT_URL"
REAL_URL=$(curl -sSIL -D - $CURRENT_URL | sed -n '1,200p' | grep location: | head -1 | sed 's/location: //')
echo REAL_URL=$REAL_URL

# now fetch, and let curl get the filename from the "real" URL
echo "# Writing to $OUT_DIR"
echo curl -L -O --output-dir "'$OUT_DIR'" "'$REAL_URL'"
curl -L -O --output-dir "$OUT_DIR" "$REAL_URL"
RC=$?
if [ "$RC" -ne "0" ]; then
	echo "ERROR RC=$RC: curl $REAL_URL" 
	exit $RC
fi

echo "# QC"
VMR_NAME=$(basename $VMR_URL)
ls -ls $OUT_DIR/$VMR_NAME
