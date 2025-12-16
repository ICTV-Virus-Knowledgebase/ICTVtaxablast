#!/usr/bin/env bash
#
# query each "A" (additional) sequence against the blastdb of "E" sequences. 
# tabulate matches and mis-matches
#
# (This would be much faster if we merged all the query fastas)
#
#
# 20240122 runtime 
#
#SBATCH --job-name=ICTV_BLAST_A_fastas_vs_E_db_blastn17
#SBATCH --output=log.%J.%x.out
#SBATCH --error=log.%J.%x.out
#
# Number of tasks needed for this job. Generally, used with MPI jobs
# Time format = HH:MM:SS, DD-HH:MM:SS
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=1000  # in Megabytes
# 
# partition and time
#SBATCH --partition=amd-hdr100 --time=00-12:00:00
##SBATCH --partition=amd-hdr100 --time=06-06:00:00
##SBATCH --partition=medium --time=40:00:00
#
./test_e_accessions.sh -m blastn17
