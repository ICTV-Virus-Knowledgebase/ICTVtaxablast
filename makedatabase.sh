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

NUC_ALL_FASTA=./fasta_new_vmr_$EA.fna
NUC_SRC_DIR=./fasta_new_vmr_b
PROT_ALL_FASTA=./fasta_new_vmr_$EA.faa
PROT_SRC_DIR=./fasta_new_vmr_b
BLAST_NUC_DB=./blast/ICTV_VMR_${EA}_nuc
BLAST_PROT_DB=./blast/ICTV_VMR_${EA}_prot
FIRST_NUC_FASTA=$(awk 'BEGIN{FS="\t";GENUS=26;ACC=7}(NR>1){print $GENUS"/"$ACC".fna"}' $ACCESSION_TSV|head -1)
PROT_OUT_FILEPATH=$(awk 'BEGIN{FS="\t";GENUS=26;ACC=7}(NR>1){print $GENUS"/"$ACC"_prot"}' $ACCESSION_TSV|head -1)
NUC_OUT_FILEPATH=$(awk 'BEGIN{FS="\t";GENUS=26;ACC=7}(NR>1){print $GENUS"/"$ACC"_nuc"}' $ACCESSION_TSV|head -1)
FIRST_PROT_FASTA=$(awk 'BEGIN{FS="\t";GENUS=26;ACC=7}(NR>1){print $GENUS"/"$ACC".faa"}' $ACCESSION_TSV|head -1)





ACCESSION_COUNT=$(tail -n +2 $ACCESSION_TSV |wc -l)
# Concatenate all formatted FASTA files into a single file for BLAST database creation.
# Both nucleotide (column 32) and protein (column 31) FASTA files are included to ensure all relevant sequences are present.
echo "# concatenate all $ACCESSION_COUNT formatted fastas"
echo "cut -f 32 $ACCESSION_TSV | tail -n +2 | xargs cat > $NUC_ALL_FASTA"
echo "cut -f 31 $ACCESSION_TSV | tail -n +2 | xargs cat > $PROT_ALL_FASTA"
cut -f 32 $ACCESSION_TSV | tail -n +2 | xargs cat > $NUC_ALL_FASTA
cut -f 31 $ACCESSION_TSV | tail -n +2 | xargs cat > $PROT_ALL_FASTA
ls -lsh $NUC_ALL_FASTA
ls -lsh $PROT_ALL_FASTA
echo "# Make the BLAST database"
if [ "$(which makeblastdb 2>/dev/null)" == "" ]; then 
    echo "module load BLAST"
    module load BLAST
fi

echo 'makeblastdb -in $NUC_ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLAST_NUC_DB" -dbtype "nucl"'
makeblastdb -in $NUC_ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLAST_NUC_DB" -dbtype "nucl"
echo 'makeblastdb -in $PROT_ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLAST_PROT_DB" -dbtype "prot"'
makeblastdb -in $PROT_ALL_FASTA -input_type "fasta" -title "ICTV VMR_MSL40.v1.20250307 ($EA)" -out "$BLAST_PROT_DB" -dbtype "prot"

echo "# Example usage:"
echo "# mkdir -p ./results/$EA/$(dirname $NUC_OUT_FILEPATH)"
echo "# mkdir -p ./results/$EA/$(dirname $PROT_OUT_FILEPATH)"
echo "# CSV output"
echo "# blastn -db $BLAST_NUC_DB -query $NUC_SRC_DIR/$FIRST_NUC_FASTA -out ./results/$EA/${NUC_OUT_FILEPATH}.csv -outfmt '7 delim=,'"
echo "# blastp -db $BLAST_PROT_DB -query $PROT_SRC_DIR/$FIRST_PROT_FASTA -out ./results/$EA/${PROT_OUT_FILEPATH}.csv -outfmt '7 delim=,'"
echo "# HTML output"
echo "# blastn -db $BLAST_NUC_DB -query $NUC_SRC_DIR/$FIRST_NUC_FASTA -out ./results/$EA/${NUC_OUT_FILEPATH}.asn -outfmt '11'"
echo "# blastp -db $BLAST_PROT_DB -query $PROT_SRC_DIR/$FIRST_PROT_FASTA -out ./results/$EA/${PROT_OUT_FILEPATH}.asn -outfmt '11'"
echo "# blast_formatter -archive ./results/$EA/${NUC_OUT_FILEPATH}.asn -out ./results/$EA/${NUC_OUT_FILEPATH}.html -html"
echo "# blast_formatter -archive ./results/$EA/${PROT_OUT_FILEPATH}.asn -out ./results/$EA/${PROT_OUT_FILEPATH}.html -html"


