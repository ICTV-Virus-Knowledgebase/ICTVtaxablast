#!/usr/bin/env bash
#
# Create conda env 
#
conda create $* \
	-p ./conda/vmr \
	-c bioconda -c conda-forge \
	pandas \
	Pyarrow \
	openpyxl=3 \
	xlrd \
	numpy \
	biopython \
	bioframe \
	natsort

