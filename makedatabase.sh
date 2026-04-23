#!/usr/bin/env bash
EA=B
VMR_PATH=VMRs/VMR_MSL40.v1.20250307_test_with_longest.xlsx
#VMR_PATH=VMRs/VMR_MSL40.v2.20251013.xlsx
if [[ "$1" == -h* ]]; then cat <<EOT
#
# Make taxaBLAST blast databases
# 
# SYNTAX: makedatabase.sh [-ea A|E|B] [-i VMR.xlsx]
# Defaults:
#    -ea $EA
#    -i  $VMR_PATH
#
EOT
	exit 0
fi

# parse args
while [[ "$1" == -* ]]; do
	# exemplar/additional/both 
	if [ "$1" == "-ea" ]; then
	    EA=$2
	    shift 2

	# VMR filename
	elif [ "$1" == "-i" ]; then
	    if [[ -z "$2" ]]; then 
		echo "ERROR: missing argument: -i VMR.xlsx"
		exit 1
	    elif [[ -e "$2" ]]; then 
		VMR_PATH="$2"
	    else
		if [[ -e VMRs/$2 ]]; then 
		    VMR_PATH=VMRs/$2
		else 	
		    echo "ERROR: input VMR.xlsx file not found: $2"
		    exit 1
		fi
	    fi
	    shift 2
	# ERROR unknown arg
	elif [[ "$1" == -* ]]; then
	    echo "ERROR: unknown flag: $1"
	    exit 1
	fi
done

# 
# computed variables
#
EA=$(echo ${EA}| tr '[:upper:]' '[:lower:]')  # lower case - both linux and mac
ACCESSION_TSV=processed_accessions_${EA}.fa_names.tsv
ACCESSION_COUNT=$(tail -n +2 $ACCESSION_TSV |wc -l)
TSV_COL_ACC=6
TSV_COL_GENUS=25
TSV_COL_FASTA_GB=31
TSV_COL_FASTA_PROT=32
TSV_COL_FASTA_NUC=33
VMR_FILE=$(basename $VMR_PATH)
ALL_FASTA=./fasta_new_vmr_${EA}.fa
FASTA_DIR=./fasta_new_vmr_${EA}
SRC_DIR=$(dirname $ALL_FASTA)

##### QQQ scan for _NUC_ and _PROT_ and change to prefix

# NUC db
NUC_ALL_FASTA=./fasta_new_vmr_${EA}.fna
NUC_BLASTDB=./blast/ICTV_VMR_${EA}_nuc
NUC_FIRST_FASTA=$(awk -v FS='\t' -v GENUS="$TSV_COL_GENUS" -v ACC="$TSV_COL_ACC" 'NR>1 {print $GENUS"/"$ACC".fna"}' "$ACCESSION_TSV" | head -1)
NUC_OUT_FILEPATH=$(awk -v FS='\t' -v GENUS="$TSV_COL_GENUS" -v ACC="$TSV_COL_ACC" 'NR>1 {print $GENUS"/"$ACC"_nuc"}' "$ACCESSION_TSV" | head -1)

# PROT db
PROT_ALL_FASTA=./fasta_new_vmr_${EA}.faa
PROT_BLASTDB=./blast/ICTV_VMR_${EA}_prot
PROT_FIRST_FASTA=$(awk -v FS='\t' -v GENUS="$TSV_COL_GENUS" -v ACC="$TSV_COL_ACC" 'NR>1 {print $GENUS"/"$ACC".faa"}' "$ACCESSION_TSV" | head -1)
PROT_OUT_FILEPATH=$(awk -v FS='\t' -v GENUS="$TSV_COL_GENUS" -v ACC="$TSV_COL_ACC" 'NR>1 {print $GENUS"/"$ACC"_prot"}' "$ACCESSION_TSV" | head -1)


cat <<EOF
# ======================================================================
# 
# parse/echo paramters
# 
# ======================================================================
EOF
echo "# -- GENERAL --"
echo "EA=${EA}"
echo "ACCESSION_TSV=$ACCESSION_TSV"
echo "VMR_PATH=$VMR_PATH"
echo "VMR_FILE=$VMR_FILE"
echo "# ---- NUC ----"
echo "NUC_ALL_FASTA=$NUC_ALL_FASTA"
echo "NUC_BLASTDB=$NUC_BLASTDB"
echo "NUC_FIRST_FASTA=$NUC_FIRST_FASTA"
echo "NUC_OUT_FILEPATH=$NUC_OUT_FILEPATH"
echo "# ---- PROT ---"
echo "PROT_ALL_FASTA=$PROT_ALL_FASTA"
echo "PROT_BLASTDB=$PROT_BLASTDB"
echo "PROT_FIRST_FASTA=$PROT_FIRST_FASTA"
echo "PROT_OUT_FILEPATH=$PROT_OUT_FILEPATH"

#
# more validatation
#
if [ ! -e "$ACCESSION_TSV" ]; then
    echo "# ERROR: missing input file: $ACCESSION_TSV"
    echo "# SOLUTION: go run: "
    echo "    ./VMR_to_fasta.py -ea $EA -mode VMR    -VMR_file_name VMRs/$VMR_FILE"
    echo "    ./VMR_to_fasta.py -ea $EA -mode fasta  -email \$USER@uab.edu -verbose"
    exit 1
fi


#
# check for failed downloads
#
EMPTY_RAWS=$(find $FASTA_DIR -size 0 \( -name "*.gb" -o -name "*.fna" \) \! -name "nan.raw")
if [[ ! -z "$EMPTY_RAWS" ]]; then
	echo "ERROR: empty files in the $FASTA_DIR fasta download/formatting cache"
	echo "# delete them using "
	echo "#     find $FASTA_DIR -size 0 \! -name 'nan.raw' -exec rm {} +"
	echo "# then re-download using "
	echo "#     ./VMR_to_fasta.py -ea $EA -mode fasta  -email \$USER@uab.edu -verbose"
	find $FASTA_DIR -size 0 \! -name "nan.raw"
	exit 1
fi

# 
# check column numbers
#
COL_NAME="Accession"
COL_NUM=$TSV_COL_ACC
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $COL_NUM)
if [[ "$COL_HEADER" != "$COL_NAME" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER' not '$COL_NAME'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER'"
fi

COL_NAME="Genus"
COL_NUM=$TSV_COL_GENUS
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $COL_NUM)
if [[ "$COL_HEADER" != "$COL_NAME" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER' not '$COL_NAME'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER'"
fi

COL_NAME="accession_aa_fasta"
COL_NUM=$TSV_COL_FASTA_PROT
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $COL_NUM)
if [[ "$COL_HEADER" != "$COL_NAME" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER' not '$COL_NAME'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER'"
fi


COL_NAME="accession_nt_fasta"
COL_NUM=$TSV_COL_FASTA_NUC
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $COL_NUM)
if [[ "$COL_HEADER" != "$COL_NAME" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER' not '$COL_NAME'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $COL_NUM is '$COL_HEADER'"
fi

#
# merge fastas to build fasta_all
#
cat <<EOF
# ======================================================================
#
# concatenate all $ACCESSION_COUNT formatted fastas 
#
# ======================================================================
EOF
echo "# -- PROT ----------"
echo "cut -f $TSV_COL_FASTA_PROT $ACCESSION_TSV | tail -n +2 | grep -v nan.fa | xargs cat > $PROT_ALL_FASTA"
cut -f $TSV_COL_FASTA_PROT $ACCESSION_TSV | tail -n +2 |  grep -v nan.fa |xargs cat > $PROT_ALL_FASTA
ls -lsh $PROT_ALL_FASTA
echo "# sequences: $(grep -c ">" $PROT_ALL_FASTA)"
echo "# -- NUC ----------"
echo "cut -f $TSV_COL_FASTA_NUC $ACCESSION_TSV | tail -n +2 | grep -v nan.fa | xargs cat > $NUC_ALL_FASTA"
cut -f $TSV_COL_FASTA_NUC $ACCESSION_TSV | tail -n +2 |  grep -v nan.fa |xargs cat > $NUC_ALL_FASTA
ls -lsh $NUC_ALL_FASTA
echo "# sequences: $(grep -c ">" $NUC_ALL_FASTA)"

cat <<EOF
# ======================================================================
# 
# Make the BLAST database
# 
# ======================================================================
EOF
if [ "$(which makeblastdb 2>/dev/null)" == "" ]; then 
    echo "module load BLAST"
    module load BLAST
fi
echo "# -- NUC --"
cat <<EOF 
makeblastdb -in $NUC_ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE [$EA] genomic" -out "$NUC_BLASTDB" -dbtype "nucl"
EOF
makeblastdb -in $NUC_ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE [$EA] genomic" -out "$NUC_BLASTDB" -dbtype "nucl"
echo "# -- PROT --"
cat <<EOF
makeblastdb -in $PROT_ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE [$EA] protein" -out "$PROT_BLASTDB" -dbtype "prot"
EOF
makeblastdb -in $PROT_ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE [$EA] protein" -out "$PROT_BLASTDB" -dbtype "prot"


echo <<EOF
# ======================================================================
# 
# Example usage:
# 
# ======================================================================
# -- NUC --
mkdir -p ./results/$EA/$(dirname $NUC_OUT_FILEPATH)
# direct to CSV output
blastn -db $NUC_BLASTDB -query $fasta_dir/$NUC_FIRST_FASTA -out ./results/$EA/${NUC_OUT_FILEPATH}.csv -outfmt '7 delim=,' 
# HTML output via ASN
blastn -db $NUC_BLASTDB -query $fasta_dir/$NUC_FIRST_FASTA -out ./results/$EA/${NUC_OUT_FILEPATH}.asn -outfmt '11' 
blast_formatter -archive ./results/$EA/${NUC_OUT_FILEPATH}.asn -out ./results/$EA/${NUC_OUT_FILEPATH}.html -html
# -- PROT --
mkdir -p ./results/$EA/$(dirname $PROT_OUT_FILEPATH)
# direct to CSV output
blastp -db $PROT_BLASTDB -query $fasta_dir/$PROT_FIRST_FASTA -out ./results/$EA/${PROT_OUT_FILEPATH}.csv -outfmt '7 delim=,'
# HTML output via ASN
blastp -db $PROT_BLASTDB -query $fasta_dir/$PROT_FIRST_FASTA -out ./results/$EA/${PROT_OUT_FILEPATH}.asn -outfmt '11'
blast_formatter -archive ./results/$EA/${PROT_OUT_FILEPATH}.asn -out ./results/$EA/${PROT_OUT_FILEPATH}.html -html

EOF
