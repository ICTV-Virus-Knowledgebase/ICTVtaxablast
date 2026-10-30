#!/usr/bin/env bash
#
# test run our docker image
#
TESTS="nuc/blastn prot/blastp"
if [[ ! -z "$1" && "$1" != -* ]]; then TESTS="$1"; shift; fi

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


#
# run list of tests
# 
for SPEC in $TESTS; do 

    #
    # for this test
    #
    TEST=$(echo $SPEC | cut -d / -f 1)
    TASK=$(echo $SPEC | cut -d / -f 2)
    echo "# --------------------------------"
    echo "# TEST=$TEST "
    echo "# TASK=$TASK "
    echo "# --------------------------------"
    TEST_DIR=./test_data/$TEST
    OUT_DIR=./test_out/$TEST/$TASK
    mkdir -p $OUT_DIR
    #echo "# cleaning out $TEST_DIR/..."
    #echo "find testResultsDocker/$TEST -name '*new*' -o -name '*diff*' -exec rm {} +"
    #find testResultsDocker/$TEST -name '*new*' -o -name '*diff*' -exec rm {} +

    echo sudo docker run -it \
	 -v "${TEST_DIR}:/seq_in" \
	 -v "${OUT_DIR}:/tax_out" \
	 ${DOCKER_CONTAINER_NAME} \
	 ./taxablast -task $TASK \
	 $*

    sudo docker run -it \
	 -v "${TEST_DIR}:/seq_in" \
	 -v "${OUT_DIR}:/tax_out" \
	 ${DOCKER_CONTAINER_NAME} \
	 ./taxablast -task $TASK \
	 $*


    echo "# validate"
    OUT=$OUT_DIR/tax_results.json
    GOOD=./test_data/results/$TEST/$TASK/tax_results.json
    echo diff $GOOD $OUT
    diff $GOOD $OUT

    echo diff -y $GOOD $OUT
    diff -y $GOOD $OUT

done
