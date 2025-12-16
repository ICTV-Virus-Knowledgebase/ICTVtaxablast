#!/usr/bin/env bash
#
# test run our docker image
#
TEST=one_seq
if [[ ! -z "$1" && "$1" != -* ]]; then TEST="$1"; shift; fi
echo TEST=$TEST
TEST_DIR=./test_data/$TEST
OUT_DIR=./test_out/$TEST
mkdir -p $OUT_DIR
#echo "# cleaning out $TEST_DIR/..."
#echo "find testResultsDocker/$TEST -name '*new*' -o -name '*diff*' -exec rm {} +"
#find testResultsDocker/$TEST -name '*new*' -o -name '*diff*' -exec rm {} +

echo sudo docker run -it \
	-v "${TEST_DIR}:/seq_in" \
	-v "${OUT_DIR}:/tax_out" \
	ictv_seqsearch \
	$*

sudo docker run -it \
	-v "${TEST_DIR}:/seq_in" \
	-v "${OUT_DIR}:/tax_out" \
	ictv_seqsearch \
	$*


echo "# validate"
OUT=$OUT_DIR/tax_results.json
GOOD=$OUT_DIR/tax_results.json.good
echo diff $GOOD $OUT
diff $GOOD $OUT

echo diff -y $GOOD $OUT
diff -y $GOOD $OUT
