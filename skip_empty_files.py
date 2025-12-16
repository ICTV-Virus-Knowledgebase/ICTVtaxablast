import os, pandas as pd, glob
import pandas.io.common

#how to skip empty files in a directory for dfs and merge dfs



path = "test_out/one_seq"
files_list = glob.glob(os.path.join(path, "*.fa.csv"))

for file in files_list:
    try:
        raw_data = pd.read_csv(file)
        # Process the file only if it's successfully read
        df = pd.read_csv(file, header=0, names=["qseqid", "sseqid", "pidentlength", "mismatch", "gaopen", "qstart", "qend", "sstart", "send", "evalue", "bitscore"])
        df2= pd.read_csv("processed_accessions_b.tsv", sep="\t", header=0)
        df["sBaseAccession"]= df["sseqid"].astype(str).str.replace(r'\.\d+.*$','',regex=True)
        merge_dfs= pandas.merge(df,df2, left_on="sBaseAccession", right_on= "Accession", how="left")

        myvar = pd.DataFrame(merge_dfs)
        print(myvar)
    except pd.errors.EmptyDataError:
        print(file, "is empty and has been skipped.")

         
         