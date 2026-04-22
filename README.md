<h1>VMR_to_BlastDB</h1>

This is a set of tools to extract data from the Virial Metadata Resource(VMR) published by the ICTV and build a	query-by-sequence database and application from it.

<h2>commands</h2>

 * [VMR_to_fasta.py](./VMR_to_fasta.py) - script for	processing VMR.xlsx and intermediate files
 * [ncbi_pull_refseq.sh](./ncbi_pull_refseq.sh) - pipeline to query refseq accessions from genbank accessions
 * [docker_build_image.sh](./docker_build_image.sh) - build Docker	image for query-by-sequence app
 * [run_pipeline_for_new_msl.sh](./run_pipeline_for_new_msl.sh) - from xls to blast_db

<h2>Requirements</h2>

1. Python 3.*
2. Pandas, including openpyxl. 
3. Numpy
4. Biopython
5. A VMR excel file placed in the directory ./VMRs

NOTE: For Blast capabilities, a verison of BLASTDB also needs to be installed. 

To create conda environments:
   * [./create_conda_env.sh](./create_conda_env.sh)
   * [./create_conda_env_openpyxl3.sh](./create_conda_env_openpyxl3.sh)
   * [./create_conda_env_openpyxl3_blast240.sh](./create_conda_env_openpyxl3_blast240.sh)

<h2>Quick Start/Test</h2>

```
# clone repo
git clone git@github.com:ICTV-Virus-Knowledgebase/ICTVtaxablast.git ICTVtaxablastp
cd !$

# setup env
./create_conda_env.sh
conda activate conda/vmr

# parse VMR.xlsx -> processed_accessions_b.tsv
./VMR_to_fasta.py -mode VMR -ea B -VMR_file_name VMRs/VMR_MSL40.v1.20250307_test_with_longest.xlsx -v

# fetch fastas from NCBI and reformat headers
./VMR_to_fasta.py -mode fasta -ea b -email $USER@uab.edu -v

# QC download - compare accessions in .fna/.faa to VMR accession lists
diff --color <(cut -f 6 processed_accessions_b.tsv | tail -n +2 |sort) <(find fasta_new_vmr_b -name "*.gb" -exec awk '/^ACCESSION/{print $2}' {} +| sort )
# QC protein extraction - not quite consistent, yet....
diff --color <(cut -f 2 processed_proteins.tsv     | tail -n +2 | cut -d . -f 1 | sort |uniq) <(find fasta_new_vmr_b -name "*.faa" -exec grep ">" {} + | cut -d - -f 4 | cut -d . -f 1  | sort | uniq )
echo "count processed_proteins.tsv: "\
    "total=$(cut -f 2 processed_proteins.tsv     | tail -n +2 | cut -d . -f 1| wc -l), "\
    " unique=$(cut -f 2 processed_proteins.tsv     | tail -n +2 | cut -d . -f 1 | sort |uniq | wc -l )"
echo "count protein_id in *.faa: "\
    " total=$(find fasta_new_vmr_b -name '*.faa' -exec grep '>' {} + | cut -d - -f 4 | cut -d . -f 1|wc -l), " \
    " unique=$(find fasta_new_vmr_b -name '*.faa' -exec grep '>' {} + | cut -d - -f 4 | cut -d . -f 1  | sort | uniq | wc -l)"


# build db databases (prot and nuc)
./makedatabase.sh -i VMRs/VMR_MSL40.v1.20250307_test_with_longest.xlsx

# search test sequences
./version_git.sh

#
# test each search task, and diff expected results
#
DB=nuc;IN=$DB;TASK=blastn
./taxablast -task $TASK -indir test_data/$IN/ -out test_out/$DB/$TASK/
diff -w -u test_data/results/$DB/$TASK/tax_results.json test_out/$DB/$TASK/tax_results.json | dwdiff --diff-input --color -P

DB=nuc;IN=$DB;TASK=megablast
./taxablast -task $TASK -indir test_data/$IN/ -out test_out/$DB/$TASK/
diff -w -u test_data/results/$DB/$TASK/tax_results.json test_out/$DB/$TASK/tax_results.json | dwdiff --diff-input --color -P

DB=nuc;IN=$DB;TASK=dc-megablast
./taxablast -task $TASK -indir test_data/$IN/ -out test_out/$DB/$TASK/
diff -w -u test_data/results/$DB/$TASK/tax_results.json test_out/$DB/$TASK/tax_results.json | dwdiff --diff-input --color -P

DB=prot;IN=$DB;TASK=blastp
./taxablast -task $TASK -indir test_data/$IN/ -out test_out/$DB/$TASK/
diff -w -u test_data/results/$DB/$TASK/tax_results.json test_out/$DB/$TASK/tax_results.json | dwdiff --diff-input --color -P

DB=prot;IN=nuc;TASK=blastx
./taxablast -task $TASK -indir test_data/$IN/ -out test_out/$DB/$TASK/
diff -w -u test_data/results/$DB/$TASK/tax_results.json test_out/$DB/$TASK/tax_results.json | dwdiff --diff-input --color -P

```

<h2>Usage - VMR_to_fasta.py</h3>

  Main script is VMR_to_fasta.py. The process is broken into steps via a argument dubbed "mode". 

<h3>Parse: -mode VMR</h3>

  To parse the VMR and extract Accession numbers(mode:VMR):
  
    ./VMR_to_fasta.py -mode VMR -ea [E|A|B] -VMR_file_name [PATH_TO_VMR.xlsx]
  
<h3>Download: -mode fasta</h3>

  To download fasta data from NCBI:
  
    ./VMR_to_fasta.py -mode fasta -ea [E|A|B] -email [your_email]
    
<h3>Build database</h3>

  Once the fastas are all downloaded (*.raw) and have had their header lines updated (.fa), we need to merge all the fastas and build a blastdb from the resulting file. Note
   * hardcoded to "-ea b":
   * reads in:          ./processed_accessions_b.tsv
   * writes FASTAs to:  ./fasta_new_vmr_b/
   * writes BLASTdb to: ./blast/ICTV_VMR_b.*

```
  # local build of test database (on mac)
  ./makedatabase.sh
```
or
```
  # submit cluster job (cheaha)
  sbatch ./makedatabase.sh
```

<h3>Test Query</h3>

Query for something in the test VMR.

CSV output: 
```
# CSV output (fmt=7)

#For blastn
blastn -db ./blast/ICTV_VMR_b -query ./fasta_new_vmr_b/Eponavirus/MG711462.fna -out ./results/e/Eponavirus/MG711462.csv  -outfmt '7 delim=,'"
#For blastp
blastp -db ./blast/ICTV_VMR_b_prot -query ./fasta_new_vmr_b/Kayvirus/AY954969.faa -out ./results/b/Kayvirus/AY954969_prot.csv -outfmt '7 delim=,'
```

HTML output: 
```
# basic HTML output
blastn -query  ./fasta_new_vmr_b/Kayvirus/AY954969.fa \
       -db     ./blast/ICTV_VMR_b
       -out    ./results/AY954969.asn \
       -outfmt 11

blast_formatter -archive ./results/AY954969.asn \
                -out     ./results/AY954969.html \
                -html
```
