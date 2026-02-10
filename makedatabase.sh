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
# 20240117 runtime ~7h, RAM=402M
#
#SBATCH --job-name=ICTV_VMR_makeblastdb_e
#SBATCH --output=logs/log.%J.%x.out
#SBATCH --error=logs/log.%J.%x.out
#
# Number of tasks needed for this job. Generally, used with MPI jobs
# Time format = HH:MM:SS, DD-HH:MM:SS
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=amd-hdr100 --time=00-12:00:00
##SBATCH --partition=amd-hdr100 --time=06-06:00:00
##SBATCH --partition=medium --time=40:00:00
#
# Number of CPUs allocated to each task. 
#
# Mimimum memory required per allocated  CPU  in  MegaBytes. 
#  last run was 402M
#SBATCH --mem-per-cpu=30000
#

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
EA=$(echo $EA| tr '[:upper:]' '[:lower:]')  # lower case - both linux and mac
ACCESSION_TSV=processed_accessions_$EA.fa_names.tsv
TSV_COL_ACC=6
TSV_COL_GENUS=25
TSV_COL_FASTA=30
VMR_FILE=$(basename $VMR_PATH)
ALL_FASTA=./fasta_new_vmr_$EA.fa
FASTA_DIR=./fasta_new_vmr_$EA
SRC_DIR=$(dirname $ALL_FASTA)
BLASTDB=./blast/ICTV_VMR_$EA
FIRST_FASTA=$(awk  'BEGIN{FS="\t";GENUS=25;ACC=6}(NR>1){print $GENUS"/"$ACC".fa"}' $ACCESSION_TSV|head -1)
OUT_FILEPATH=$(awk 'BEGIN{FS="\t";GENUS=25;ACC=6}(NR>1){print $GENUS"/"$ACC}'      $ACCESSION_TSV|head -1)

#
# echo params
#
echo "EA=$EA"
echo "ACCESSION_TSV=$ACCESSION_TSV"
echo "VMR_PATH=$VMR_PATH"
echo "VMR_FILE=$VMR_FILE"
echo "ALL_FASTA=$ALL_FASTA"
echo "SRC_DIR=$SRC_DIR"
echo "BLASTDB=$BLASTDB"
echo "FIRST_FASTA=$FIRST_FASTA"
echo "OUT_FILEPATH=$OUT_FILEPATH"

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
EMPTY_RAWS=$(find $FASTA_DIR -size 0 \! -name "nan.raw")
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
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $TSV_COL_ACC)
if [[ "$COL_HEADER" != "Accession" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $TSV_COL_ACC is '$COL_HEADER' not 'Accession'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $TSV_COL_ACC is '$COL_HEADER'"
fi

COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $TSV_COL_GENUS)
if [[ "$COL_HEADER" != "Genus" ]]; then
	echo "OK: ${ACCESSION_TSV} col $TSV_COL_GENUS is '$COL_HEADER' not 'Genus'"
	exit 1
else
	echo "ERROR: ${ACCESSION_TSV} col $TSV_COL_GENUS is '$COL_HEADER'"
fi
COL_HEADER=$(head -1 $ACCESSION_TSV | cut -f $TSV_COL_FASTA)
if [[ "$COL_HEADER" != "accession_fa_file_name" ]]; then
	echo "ERROR: ${ACCESSION_TSV} col $TSV_COL_GENUS is '$COL_HEADER' not 'accession_fa_file_name'"
	exit 1
else
	echo "OK: ${ACCESSION_TSV} col $TSV_COL_GENUS is '$COL_HEADER'"
fi


ACCESSION_COUNT=$(tail -n +2 $ACCESSION_TSV | grep -v nan.fa | wc -l)
echo "# concatenate all $ACCESSION_COUNT formatted fastas "
echo "# from $SRC_DIR into $ALL_FASTA"
echo "cut -f $TSV_COL_FASTA $ACCESSION_TSV | tail -n +2 | grep -v nan.fa | xargs cat > $ALL_FASTA"
cut -f $TSV_COL_FASTA $ACCESSION_TSV | tail -n +2 | grep -v nan.fa | xargs cat > $ALL_FASTA
ls -lsh $ALL_FASTA
echo "# sequences: $(grep -c ">" $ALL_FASTA)"

echo " "
echo "# Make the BLAST database"
if [ "$(which makeblastdb 2>/dev/null)" == "" ]; then 
    echo "module load BLAST"
    module load BLAST
fi

echo 'makeblastdb -in $ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE ($EA)" -out "$BLASTDB" -dbtype "nucl"'
makeblastdb -in $ALL_FASTA -input_type "fasta" -title "ICTV $VMR_FILE ($EA)" -out "$BLASTDB" -dbtype "nucl"

echo "# Example usage:"
echo "# mkdir -p ./results/$EA/$(dirname $OUT_FILEPATH)"
echo "# CSV output"
echo "# blastn -db $BLASTDB -query $FASTA_DIR/$FIRST_FASTA -out ./results/$EA/${OUT_FILEPATH}.csv -outfmt '7 delim=,'"
echo "# HTML output"
echo "# blastn -db $BLASTDB -query $FASTA_DIR/$FIRST_FASTA -out ./results/$EA/${OUT_FILEPATH}.asn -outfmt '11'"
echo "# blast_formatter -archive ./results/$EA/${OUT_FILEPATH}.asn -out ./results/$EA/${OUT_FILEPATH}.html -html"

