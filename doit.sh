module load BLAST

echo blastn -task blastn -word_size 10 -db ./blast/ICTV_VMR_e -query ./fasta_new_vmr_a/Kayvirus/JX080302.fa -out results/blastn10_test/a/Keyvirus/JX080302.7.qcovs.qcovus.hit10.csv -outfmt '7 qseqid sseqid qcovs qcovus' -max_target_seqs 10 
nohup blastn -task blastn -word_size 10 -db ./blast/ICTV_VMR_e -query ./fasta_new_vmr_a/Kayvirus/JX080302.fa -out results/blastn10_test/a/Keyvirus/JX080302.7.qcovs.qcovus.hit10.csv -outfmt '7 qseqid sseqid qcovs qcovus' -max_target_seqs 10 2>&1 > logs/test_Kayvirus_JX080302_7.qcovs.qcovus.hit10.txt &


echo blastn -task blastn -word_size 10 -db ./blast/ICTV_VMR_e -query ./fasta_new_vmr_a/Kayvirus/JX080302.fa -out results/blastn10_test/a/Keyvirus/JX080302.7.qcovs.hit10.csv -outfmt '7 qseqid sseqid qcovs' -max_target_seqs 10 
nohup blastn -task blastn -word_size 10 -db ./blast/ICTV_VMR_e -query ./fasta_new_vmr_a/Kayvirus/JX080302.fa -out results/blastn10_test/a/Keyvirus/JX080302.7.qcovs.hit10.csv -outfmt '7 qseqid sseqid qcovs' -max_target_seqs 10 2>&1 > logs/test_Kayvirus_JX080302_7.qcovs.hit10.txt &

echo "$(date) waiting..."
wait
echo "$(date) DONE"


