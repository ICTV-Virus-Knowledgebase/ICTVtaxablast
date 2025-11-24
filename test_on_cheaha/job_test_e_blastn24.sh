#!/usr/bin/env bash
#
# query each "A" (additional) sequence against the blastdb of "E" sequences. 
#
# split by genus
#
#
#
GENERA=$(cd ../fasta_new_vmr_a/;ls -ls|grep drwx|sed 's/.* //g')
for GENUS in $GENERA; do
    sbatch --job-name ICTV_BLAST_A_fastas_vs_E_db_blastn24_$GENUS ./test_e_accessions.sh -g $GENUS -m blastn24 
done

