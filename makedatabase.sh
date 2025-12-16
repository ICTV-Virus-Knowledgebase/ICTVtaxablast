#!/usr/bin/env bash
#
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
EA=b
if [ "$1" == "-ea" ]; then
    EA=$2
    shift 2
fi
echo "EA=$EA"
ACCESSION_TSV=processed_accessions_$EA.fa_names.tsv
# validate
if [ ! -e "$ACCESSION_TSV" ]; then
    echo "# ERROR: missing input file: $ACCESSION_TSV"
    echo "# SOLUTION: go run: "
    echo "    ./VMR_to_fasta.py -ea $EA -mode VMR    -VMR_file_name VMRs/VMR_MSL40.v1.20250307.xlsx"
    echo "    ./VMR_to_fasta.py -ea $EA -mode fasta  -email \$USER@uab.edu -verbose"
    exit 1
fi

ALL_FASTA=./fasta_new_vmr_$EA.fa
SRC_DIR=$(dirname $ALL_FASTA)
BLASTDB=./blast/ICTV_VMR_$EA
FIRST_FASTA=$(awk 'BEGIN{FS="\t";GENUS=25;ACC=6}(NR>1){print $GENUS"/"$ACC".fa"}' $ACCESSION_TSV|head -1)
OUT_FILEPATH=$(awk 'BEGIN{FS="\t";GENUS=25;ACC=6}(NR>1){print $GENUS"/"$ACC}' $ACCESSION_TSV|head -1)



ACCESSION_COUNT=$(tail -n +2 $ACCESSION_TSV |wc -l)
echo "# concatenate all $ACCESSION_COUNT formatted fastas"
echo "cut -f 31 $ACCESSION_TSV | tail -n +2 | xargs cat > $ALL_FASTA"
cut -f 31 $ACCESSION_TSV | tail -n +2 | xargs cat > $ALL_FASTA
ls -lsh $ALL_FASTA

echo "# Make the BLAST database"
if [ "$(which makeblastdb 2>/dev/null)" == "" ]; then 
    echo "module load BLAST"
    module load BLAST
fi

echo 'makeblastdb -in $ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLASTDB" -dbtype "nucl"'
makeblastdb -in $ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLASTDB" -dbtype "nucl"

echo "# Example usage:"
echo "# mkdir -p ./results/$EA/$(dirname $OUT_FILEPATH)"
echo "# CSV output"
echo "# blastn -db $BLASTDB -query ./$SRC_DIR/$FIRST_FASTA -out ./results/$EA/${OUT_FILEPATH}.csv -outfmt '7 delim=,'"
echo "# HTML output"
echo "# blastn -db $BLASTDB -query ./$SRC_DIR/$FIRST_FASTA -out ./results/$EA/${OUT_FILEPATH}.asn -outfmt '11'"
echo "# blast_formatter -archive ./results/$EA/${OUT_FILEPATH}.asn -out ./results/$EA/${OUT_FILEPATH}.html -html"

