#!/usr/bin/env python3
#
# VMR_to_fasta.py
#
# Extract accessions and lineages from VMR.xls, query NCBI, build VMR.blast_db, query VMR.blast_db
#
# INPUT: 
#     -VMR_file_name VMRs/VMR_MSL39_v3.xlsx
# ARGS: 
#     -      
# ITERMEDIATE FILES:
print("# Importing time python package")
import time
startTime = time.time()
def formatElapsedTime():
    """Returns elapsed time as a formatted string [HH]h[MM]m[SS]s"""

    elapsedTime = time.time() - startTime
    hours, remainder = divmod(int(elapsedTime), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"[{hours:02d}h{minutes:02d}m{seconds:02d}s]"

print("# {0} Importing python packages: please wait...".format(formatElapsedTime()))
import pandas as pd
import subprocess
from urllib import error
import argparse
import numpy as np
import re
import sys
import os
import pathlib # for stem=basename(.txt)
import csv

# Class needed to load args from files. 
class LoadFromFile (argparse.Action):
    def __call__ (self, parser, namespace, values, option_string = None):
        with values as f:
            # parse arguments in the file and store them in the target namespace
            parser.parse_args(f.read().split(), namespace)
parser = argparse.ArgumentParser(description="")

#setting arguments.
print("# {0} Parsing args...".format(formatElapsedTime()))

parser.add_argument('-verbose',help="printout details during run",action=argparse.BooleanOptionalAction)
parser.add_argument('-tmi',help="printout Too Much Information during run",action=argparse.BooleanOptionalAction)
parser.add_argument('-file',help="optional argument. Name of the file to get arguments from.",type=open, action=LoadFromFile)
parser.add_argument("-email",help="email for Entrez to use when fetching Fasta files")
parser.add_argument("-mode",help="what function to do. Options: VMR,fasta,db")
parser.add_argument("-ea",help="Fetch E or A records (Exemplars or AdditionalIsolates)", default="E")
parser.add_argument("-VMR_file_name",help="name of the VMR file to load.",default="VMR_E_data.xlsx")
parser.add_argument("-fasta_dir",help="Directory to store downloaded fasta cache", default="./fasta_new_vmr_b" )
parser.add_argument("-query",help="Name of the fasta file to query the database")
parser.add_argument("-k", "--keep-going", help="log per-accession errors and continue in fasta mode", action="store_true")
args = parser.parse_args()
if args.mode != 'fasta' and args.mode != "VMR" and args.mode != "db":
    print("Valid mode not selected. Options: VMR,fasta,db",file=sys.stderr)
#Takes forever to import so only imports if it's going to be needed
if args.mode == 'fasta':
    print("Importing Entrez from Bio...")
    from Bio import Entrez
    from Bio import SeqIO
    from Bio.Seq import UndefinedSequenceError
#Catching error
if args.mode == "db":
    if args.query == None:
        print("Database Query mode is selected but no fasta file was specified! Please set the '-fasta_file_name' or change mode.",file=sys.stderr)

VMR_file_name_tsv = './vmr.tsv'
processed_accession_file_name ="./processed_accessions_"+args.ea.lower()+".tsv"


###############################################################################################################
# Loads excel from https://talk.ictvonline.org/taxonomy/vmr/m/vmr-file-repository/ and puts it into a DataFrame
# NOTE: URL is incorrect. 
############################################################################################################### 
# DataFrame['column name'] = provides entire column
# DataFrame['column name'][0,1,2,3,4,5 etc] provides row for that column
# 
#
def load_VMR_data():
    if args.verbose: print("load_VMR_data()")
    if args.verbose: print("  opening", args.VMR_file_name)

    # Importing excel sheet as a DataFrame. Requires xlrd and openpyxl package
    try:
        # open excel file
        vmr_excel = pd.ExcelFile(args.VMR_file_name,engine='openpyxl')
        if args.verbose: print("\tOpened VMR Excel file: with {0} sheets: {1}".format(len(vmr_excel.sheet_names),args.VMR_file_name))

        # find first sheet matching "^VMR MSL"
        sheet_name = next((sheet for sheet in vmr_excel.sheet_names if re.match(r"^VMR MSL", sheet)), None)
        if args.verbose: print("\tFound sheet '{0}'.".format(sheet_name))

        if sheet_name is None:
            raise ValueError("No worksheet name matching the pattern '^VMR MSL' found.")
            raise SystemExit(1)
        else:
            raw_vmr_data = pd.read_excel(args.VMR_file_name,sheet_name=sheet_name,engine='openpyxl')
            if args.verbose: print("VMR data loaded: {0} rows, {1} columns.".format(*raw_vmr_data.shape))
            if args.verbose: print("\tcolumns: ",raw_vmr_data.columns)

            # list of the columns to extract from raw_vmr_data
            vmr_cols_needed = [
                'Isolate ID','Exemplar or additional isolate','Species Sort','Isolate Sort',
                'Realm','Subrealm','Kingdom','Subkingdom','Phylum','Subphylum','Class','Subclass',
                'Order','Suborder','Family','Subfamily','Genus','Subgenus','Species',
                'ICTV_ID','Virus name(s)',
                'Virus GENBANK accession','Genome coverage']
            
            for col_name in list(raw_vmr_data.columns):
                if col_name in vmr_cols_needed:
                    print("    "+col_name+" [NEEDED]")
                else:
                    print("    "+col_name)
                    
            have_missing=False 
            for col_name in vmr_cols_needed:
                if not col_name in list(raw_vmr_data.columns):
                    print("    "+col_name+" [!MISSING!]")
                    have_missing=True
            if have_missing:
                print("Error: Required columns are missing from {0}".format(args.VMR_file_name), file=sys.stderr)
                raise SystemExit(1)

    except(FileNotFoundError):
        print("The VMR file specified does not exist! Make sure the path set by '-VMR_file_name' is correct.",file=sys.stderr)
        raise SystemExit(1)
    

    # save As TSV for diff'ing
    if os.path.exists(VMR_file_name_tsv) and os.path.getmtime(VMR_file_name_tsv) > os.path.getmtime(args.VMR_file_name):
        if args.verbose: print("  SKIP writing", VMR_file_name_tsv)
    else:
        if args.verbose: print("  writing", VMR_file_name_tsv)
        raw_vmr_data.to_csv(VMR_file_name_tsv,sep='\t', index=False)

    # compiling new dataframe from vmr_cols_needed
    #truncated_vmr_data = raw_vmr_data[vmr_cols_needed]

    # DataFrame.loc is helpful for indexing by row. Allows expression as an argument. Here, 
    # it finds every row where 'E' is in column 'Exemplar or additional isolate' and returns 
    # only the columns specified. 
    #vmr_data = truncated_vmr_data.loc[truncated_vmr_data['Exemplar or additional isolate']==args.ea.upper(),['Species Sort','Isolate Sort','Species','Virus GENBANK accession',"Genome coverage","Genus"]]
    ea_col = raw_vmr_data['Exemplar or additional isolate'].fillna('').astype(str).str.strip().str.upper()
    if args.ea.upper() == 'A' or args.ea.upper() == 'E':
        vmr_data = raw_vmr_data.loc[ea_col==args.ea.upper(),vmr_cols_needed]
    elif args.ea.upper() == 'B':
        # both e and a
        vmr_data = raw_vmr_data.loc[ea_col!='',vmr_cols_needed]

    if args.verbose: print("Filtered VMR down to "+args.ea.upper()+" records")
    if args.verbose: print("\tcolumns: ",vmr_data.columns)
    if args.verbose: print("   Filtered: {0} rows, {1} columns.".format(*vmr_data.shape))

    return vmr_data.reset_index(drop=True)

#insert(parse_seg_accession_list)
def normalize_accession(isolate_id, accession):
    if accession.endswith('.'):
        normalized_accession = accession.rstrip('.')
        return (
            normalized_accession,
            "stripped trailing '.' from accession '{0}' -> '{1}'".format(accession, normalized_accession)
        )

    normalized_accession = re.sub(r'\.\d+$', '', accession)
    if normalized_accession != accession:
        return (
            normalized_accession,
            "stripped accession version suffix from '{0}' -> '{1}'".format(accession, normalized_accession)
        )

    return accession, ""

def parse_seg_accession_list(isolate_id,acc_list_str):
    if pd.isna(acc_list_str):
        return []

    # remove whitespace.
    acc_list_str = str(acc_list_str).replace(" ","")
    if acc_list_str == '':
        return []

    # instead of trying to split by commas and semicolons, I just replace the commas with semicolons. 
    acc_list_str = acc_list_str.replace(",",";")

    # split into list: ";" 
    accession_list = acc_list_str.split(';')
    if args.tmi: print("accession_list:"+"|".join(accession_list))

    # 
    # for each [SEG:]ACCESSION
    # 
    result_arr = [] # list of seg_name-accession maps
    accession_index = 0
    for seg_acc_str in accession_list:
        if seg_acc_str == '':
            continue
        if args.tmi: print("seg_acc_str:"+seg_acc_str)

        # track accession/segment order, so it can be preserved
        accession_index += 1

        # split optional "segment_name:" prefix on accessions
        seg_acc_pair = seg_acc_str.split(':')
        segment_name = None
        accession    = None
        if len(seg_acc_pair)==0 or len(seg_acc_pair)>2:
            print("ERROR[isolate_id:"+str(isolate_id)+": [seg:]acc >1 colon: '"+str(seg_acc_pair)+"' from '"+acc_list_str+"'",file=sys.stderr)
        else:
            if len(seg_acc_pair)==1:
                # bare accession
                accession, accession_error = normalize_accession(isolate_id, seg_acc_pair[0])
                result_arr.append({"accession":accession, "segment_name":None, "accession_index":accession_index, "isolate_id":isolate_id, "error":accession_error})
                if args.tmi: print("result_arr["+str(accession_index)+"]:"+str(result_arr[accession_index-1]))
            elif len(seg_acc_pair)==2:
                # seg_name:accession
                segment_name = seg_acc_pair[0]
                accession, accession_error = normalize_accession(isolate_id, seg_acc_pair[1])
                result_arr.append({"accession":accession, "segment_name":segment_name, "accession_index":accession_index, "isolate_id":isolate_id, "error":accession_error})
                if args.tmi: print("result_arr["+str(accession_index)+"]:"+str(result_arr[accession_index-1]))

            # QC accessions
            number_count = 0
            letter_count = 0
            # counting letters
            for char in accession:
                if char in 'qwertyuiopasdfghjklzxcvbnm':
                    letter_count = letter_count+1
            # counting numbers
                elif char in '1234567890':
                    number_count = number_count+1
            #checks if current selection fits what an accession number should be
            if not (len(str(accession)) == 8 or 6 and letter_count<3 and number_count>3):
                print("ERROR[isolate_id:"+str(isolate_id)+"]: suspect accesssion '"+accession+"'",file=sys.stderr)

                
    # we'll check later if this segment has a name 
    return(result_arr)
#
# test cases
#
#print(parse_seg_accession_list(1003732,'HM246720'))
#print(parse_seg_accession_list(1003732,'NC_027989'))
#print(parse_seg_accession_list(1003732,'HM246720; HM246721; HM246722; HM246723; HM246724'))
#print(parse_seg_accession_list(1003732,'NC_027989; NC_041833; NC_041831; NC_041832; NC_041834'))
#print(parse_seg_accession_list(1007556,'DNA-C: EF546812; DNA-M: EF546811; DNA-N: EF546808; DNA-R: EF546813; DNA-S:EF546810; DNA-U3: EF546809'))
#print(parse_seg_accession_list(1007556,'DNA-C: NC_010318; DNA-M: NC_010317; DNA-N:NC_010314; DNA-R: NC_010319; DNA-S: NC_010316; DNA-U3:     NC_010315'))

def test_accession_IDs(df):
    if args.verbose: print("test_accession_IDs()")
    if args.verbose: print("\tcolumns: ",df.columns)
##############################################################################################################
# Cleans Accession numbers assuming the following about the accession numbers:
# 1. Each Accession Number is 6-8 characters long
# 2. Each Accession Number contains at least 3 numbers
# 3. Each Accession Number contains at most 3 letters
# 4. Accession Numbers in the same block are seperated by a ; or a , or a :
##############################################################################################################
    processed_accession_columns = [
        'ICTV_ID','Isolate_ID','Exemplar_Additional','Accession_Index','Segment_Name','Accession', # 0-5
        'Start_Loc','End_Loc','Sort','Isolate_Sort','Original_GENBANK_Accessions','Errors', # 6-11
        'Realm','Subrealm','Kingdom','Subkingdom','Phylum','Subphylum','Class','Subclass','Order','Suborder', # 12-21
        'Family','Subfamily','Genus','Subgenus','Species','Virus_Names' # 22-27
    ]
    # pattern for accessions qualified by "(START,STOP)" subsequence qualifiers
    accession_start_end_regex = re.compile(r'([A-Za-z0-9_]+(?:\.\d+|\.)?)\s*\((\d+)(\.)(\w+)(\))')
    processed_accession_rows = []

    # for loop for every entry in given processed_accessionIDs
    for row in df.to_dict('records'):
        #
        # split accessions list (seporarated by ;  by , )
        #

        isolate_id_str = str(row['Isolate ID'])
        # get original list of accessions
        gb_accessions_str = row['Virus GENBANK accession']
        #rs_accessions_str = str(df['Virus REFSEQ accession'][entry_count])

        # parse
        gb_accessions_dict = parse_seg_accession_list(isolate_id_str,gb_accessions_str)
        #rs_accessions_dict = parse_seg_accession_list(rs_accessions_str)

        # merge parallel lists (not nice)
        #if len(gb_accessions_dict) != rs_accessions_dict:
        #   print("WARNING[isolate:"+str(isolate_id)+"]: gb_n_acc: "+str(len(gb_accessions_dict))+" != rs_n_acc:"+str(len(rs_accessions_dict)),file=sys.stderr)


        # iterate over accessions
        for acc_dict in gb_accessions_dict:
            # default subsequence locations (none)
            start_loc=''
            end_loc=''
            # check for accessions followed by (INT,INT) 
            re_result=accession_start_end_regex.match(acc_dict['accession'])

            if re_result:
                # accession is qualified - parse out accession from START/STOP nt coords
                processed_accession, range_accession_error = normalize_accession(isolate_id_str, re_result.group(1))
                start_loc= re_result.group(2)
                end_loc  = re_result.group(4)
            else:
                # use accession as is
                processed_accession = acc_dict['accession']
                range_accession_error = ""

            accession_errors = "; ".join(
                error for error in [acc_dict.get("error", ""), range_accession_error] if error
            )
                
            processed_accession_rows.append([
                # 0-5
                row['ICTV_ID'],
                row['Isolate ID'],
                row['Exemplar or additional isolate'],
                acc_dict['accession_index'],
                acc_dict['segment_name'],
                processed_accession,
                # 6-11
                start_loc,
                end_loc,
                row['Species Sort'],
                row['Isolate Sort'],
                row['Virus GENBANK accession'],
                accession_errors, # errors
                # 12-21
                row['Realm'],
                row['Subrealm'],
                row['Kingdom'],
                row['Subkingdom'],
                row['Phylum'],
                row['Subphylum'],
                row['Class'],
                row['Subclass'],
                row['Order'],
                row['Suborder'],
                # 22-27
                row['Family'],
                row['Subfamily'],
                row['Genus'],
                row['Subgenus'],
                row['Species'],
                row['Virus name(s)'],
            ])
            #print("'"+processed_accession+"'"+' has been cleaned.')

    return pd.DataFrame.from_records(processed_accession_rows, columns=processed_accession_columns)

def sanitize_filename(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', str(value))

def fetch_entrez_text(db, accession_ID, rettype, output_file_name, entrez_sleep):
    handle = Entrez.efetch(db=db, id=accession_ID, rettype=rettype, retmode="text")
    time.sleep(entrez_sleep)
    raw_text = handle.read()
    handle.close()
    with open(output_file_name, 'w') as raw_file:
        raw_file.write(raw_text)
    return raw_text

def fetch_contig_sequence(contig_accession, genus_dir, entrez_sleep):
    contig_fasta = os.path.join(genus_dir, sanitize_filename(contig_accession)+".fna")
    if not os.path.exists(contig_fasta):
        if args.verbose: print("[FETCH]  EXEC NCBI fetch for CONTIG {0}".format(contig_accession))
        fetch_entrez_text("nuccore", contig_accession, "fasta", contig_fasta, entrez_sleep)
    elif args.verbose:
        print("[FETCH]  SKIP NCBI fetch for {0}".format(contig_fasta))

    contig_record = SeqIO.read(contig_fasta, "fasta")
    return str(contig_record.seq)

def sequence_from_genbank_record(gb_record, accession_ID, genus_dir, entrez_sleep):
    try:
        return str(gb_record.seq)
    except UndefinedSequenceError:
        contig = gb_record.annotations.get("contig")
        if not contig:
            raise

        contig_parts = re.findall(r'([A-Za-z0-9_.]+):(\d+)\.\.(\d+)', contig)
        if len(contig_parts) == 0:
            raise ValueError("undefined sequence for {0}; unsupported CONTIG expression: {1}".format(accession_ID, contig))

        sequence_parts = []
        for contig_accession, start_str, end_str in contig_parts:
            contig_seq = fetch_contig_sequence(contig_accession, genus_dir, entrez_sleep)
            start = int(start_str) - 1
            end = int(end_str)
            sequence_parts.append(contig_seq[start:end])

        if args.verbose:
            print("[FORMAT] Resolved undefined sequence for {0} from CONTIG {1}".format(accession_ID, contig))
        return ''.join(sequence_parts)

def parse_accession_range(row, accession_ID, sequence_length):
    start_loc = str(row.get("Start_Loc", "")).strip()
    end_loc = str(row.get("End_Loc", "")).strip()
    if start_loc == "" and end_loc == "":
        return None
    if start_loc == "" or end_loc == "":
        raise ValueError("accession {0} has incomplete range: start={1}, end={2}".format(accession_ID, start_loc, end_loc))

    start = int(float(start_loc))
    end = int(float(end_loc))
    if start < 1 or end < start:
        raise ValueError("accession {0} has invalid range: start={1}, end={2}".format(accession_ID, start, end))
    if end > sequence_length:
        raise ValueError("accession {0} range end {1} exceeds sequence length {2}".format(accession_ID, end, sequence_length))

    return {"start": start, "end": end, "start0": start - 1, "end0": end}

def feature_contained_in_range(feature, accession_range):
    if accession_range is None:
        return True

    feature_start = int(feature.location.start)
    feature_end = int(feature.location.end)
    return feature_start >= accession_range["start0"] and feature_end <= accession_range["end0"]

#######################################################################################################################################
# Utilizes Biopython's Entrez API to fetch FASTA data from Accession numbers. 
# Prints Accession Numbers that failed to 'clean' correctly
# 
# this should use epost to work in batches
#######################################################################################################################################  
def fetch_fasta(processed_accession_file_name):
    if args.verbose: print("fetch_fasta(",processed_accession_file_name,")")

    # make sure the output directory exists
    if not os.path.exists(args.fasta_dir):
        # Create the directory if it doesn't exist
        os.makedirs(args.fasta_dir)
        if args.verbose: print(f"Directory '{args.fasta_dir}' created successfully.")

    #file names for outputs
    bad_accessions_fname="./bad_accessions_"+args.ea.lower()+".tsv"
    #complete genome accession file
    processed_accessions_fanames_fname=processed_accession_file_name.replace(".tsv","")+".fa_names.tsv"
    #protein accessions file
    processed_protein_accessions_fname="processed_proteins.tsv"
    processed_protein_columns = ["Accession", "Protein_id", "Product_name", "Note", "Codon_start"]
    processed_protein_rows = []
    
    #Check to see if fasta data exists and, if it does, loads the accessions numbers from it into an np array.
    if args.verbose: print("  loading:", processed_accession_file_name)
    # "Acessions" was for original nt data
    Accessions = pd.read_csv(processed_accession_file_name,sep='\t')

    all_reads = []
    bad_accessions = Accessions.loc[
        Accessions["Errors"].fillna("").astype(str).str.strip() != ""
    ].fillna("").to_dict("records")

    def handle_accession_error(row, message, exception=None):
        error_row = dict(row)
        error_row["Errors"] = message
        bad_accessions.append(error_row)
        print("    [ERR] {0}".format(message), file=sys.stderr)
        if not args.keep_going:
            if exception is not None:
                raise exception
            raise RuntimeError(message)

    # NCBI Entrez Session setup
    entrez_sleep = 0.34 # 3 requests per second with email authN
    Entrez.email = args.email
    if "NCBI_API_KEY" in os.environ:
        # use API_KEY  authN (10 queries per second)
        entrez_sleep = 0.1 # 10 requrests per second with API_KEY
        Entrez.api_key = os.environ["NCBI_API_KEY"]
        if args.verbose: print("NCBI Entrez 10/second with NCBI_API_KEY")
    else: 
        # use email authN
        if args.verbose: print("NCBI Entrez 3/second with email=",args.email)

    accession_gb_paths = []
    accession_aa_fasta_paths = []
    accession_nt_fasta_paths = []

    # Fetches FASTA data for every accession number
    for count, row in enumerate(Accessions.fillna('').to_dict('records')):
            accession_ID = row['Accession']
            Isolate_ID   = row['Isolate_ID']
            Isolate_type = row['Exemplar_Additional']
            segment      = row['Segment_Name']
            family_name  = row['Family']
            genus_name   = row['Genus']
            species_name = row['Species']
            virus_names  = row['Virus_Names']
            if args.verbose: print("Fetch [",count,"] ID:",Isolate_ID," Species:",species_name," Segment:",segment," Accession:",accession_ID)

            # fasta_file_name
            genus_dir = args.fasta_dir+"/"+str(genus_name)
            if genus_name == "":
                genus_dir = args.fasta_dir+"/"+"no_genus"
            accession_gb = genus_dir+"/"+str(accession_ID)+".gb"
            accession_aa_fasta = genus_dir+"/"+str(accession_ID)+".faa"
            accession_nt_fasta = genus_dir+"/"+str(accession_ID)+".fna"

            bad_protein_len= genus_dir+"/"+str(accession_ID)+"_bad_protein_length.tsv"
            
            accession_gb_paths.append(accession_gb)
            accession_aa_fasta_paths.append(accession_aa_fasta)
            accession_nt_fasta_paths.append(accession_nt_fasta)
    
            # make sure dir exists
            if not os.path.exists(genus_dir):
                # Create the directory if it doesn't exist
                os.makedirs(genus_dir)
                if args.verbose: print(f"Directory '{genus_dir}' created successfully.")
    
            # check if the raw file exists and is non-empty
            if os.path.exists(accession_gb) and os.path.getsize(accession_gb) > 0:
                if args.verbose: print("[FETCH]  SKIP NCBI fetch for {accession_gb}".format(**locals()))
            else:
                if args.verbose:
                    if os.path.exists(accession_gb):
                        print("[FETCH]  REDO NCBI fetch for empty file {accession_gb}".format(**locals()))
                    else:
                        print("[FETCH]  EXEC NCBI fetch for {accession_gb}".format(**locals()))
                try:
                    # fetch GenBank from NCBI
                    fetch_entrez_text("nuccore", accession_ID, "gb", accession_gb, entrez_sleep)
                    if args.verbose: print('    .gb for '+accession_ID+ ' obtained.')
                    if args.verbose: print('    wrote: '+accession_gb)

                except Exception as e:
                    handle_accession_error(
                        row,
                        "Accession ID '{0}' Entrez.efetch threw an error: {1}".format(accession_ID, e),
                        e
                    )
                    continue

            # check if processed .faa & .fna fastas are out of date
            if os.path.getsize(accession_gb) == 0:
                        handle_accession_error(row, "complete record file is empty: {0}".format(accession_gb))
                        continue
            else:
#            elif os.path.exists(accession_fa_file_name) and os.path.getmtime(accession_fa_file_name) > os.path.getmtime(accession_raw_file_name):
#                if args.verbose: print("[FORMAT] SKIP reformat header for {accession_fa_file_name}".format(**locals()))
#            else:
#                if args.verbose: print("[FORMAT] EXEC reformat header for {accession_fa_file_name}".format(**locals()))
                
                try:
                    # open genbank file and read using SeqIO
                    with open(accession_gb,"r") as gb_file:
                        gb_open = SeqIO.read(gb_file, "genbank")
                    nt_sequence = sequence_from_genbank_record(gb_open, accession_ID, genus_dir, entrez_sleep)
                    accession_range = parse_accession_range(row, accession_ID, len(nt_sequence))
                except Exception as e:
                    handle_accession_error(
                        row,
                        "failed to parse sequence for accession {0} from {1}: {2}".format(accession_ID, accession_gb, e),
                        e
                    )
                    continue

                if nt_sequence:
                    output_nt_sequence = nt_sequence
                    if accession_range is not None:
                        output_nt_sequence = nt_sequence[accession_range["start0"]:accession_range["end0"]]
                        if args.verbose:
                            print("[FORMAT] Trimming {0} to {1}..{2}".format(
                                accession_ID,
                                accession_range["start"],
                                accession_range["end"]
                            ))

                    make_nt_file= open(accession_nt_fasta,'w')
                    
                    # Build FASTA header
                    version = gb_open.annotations.get("sequence_version", "1")
                    Beggining_firstline= ([species_name,"-",segment,"-",accession_ID,version,])
                    End_firstline= ([family_name,Isolate_type,virus_names])
                    Beggining_firstline= str(Beggining_firstline).replace("[","").replace("]","").replace("'","").replace(","," ")
                    Beggining_firstline= re.sub(r"\s*-\s*", "-", re.sub(r"\s+"," ", Beggining_firstline)).replace(" ", "_", 1).replace(" ", ".")
                    #end first line only needed commas and brackets replaced with spaces.
                    End_firstlineline= str(End_firstline).replace("[","").replace("]","").replace("'","").replace(","," ")
                    first_line= Beggining_firstline+" "+End_firstlineline

                    #first line of .fna file
                    make_nt_file.write(">"+first_line+"\n")


                    # sequence line of .fna file in fasta format
                    make_nt_file.write("{0}\n".format(output_nt_sequence))
                    make_nt_file.close()
                    if args.verbose: print('    wrote: '+accession_nt_fasta)

                    with open(accession_aa_fasta, "w") as make_aa_file:
                        protein_check = set()
                        for feature in gb_open.features:
                            if feature.type == "CDS" and "translation" in feature.qualifiers:
                                if not feature_contained_in_range(feature, accession_range):
                                    continue
                # Build FASTA header for protein
                                protein_id = feature.qualifiers.get("protein_id", ["unknown_protein"])[0]
                                
                                product_name = feature.qualifiers.get("product", ["unknown_product"])[0]
                                protein_count= feature.qualifiers["translation"][0].strip()
                                note_in_gb = feature.qualifiers.get("note", [""])[0]
                                codon_start = feature.qualifiers.get("codon_start", [""])[0]
                                if protein_count:
                                    protein_check.add(protein_count)


                                #first line of .faa file
                                header = f">{Beggining_firstline} {protein_id} {End_firstline} {product_name} "
                                # Remove brackets and quotes from End_firstline if it's a list
                                if isinstance(End_firstline, list):
                                    End_firstline_str = " ".join(str(x) for x in End_firstline)
                                else:
                                    End_firstline_str = str(End_firstline)
                                header = f">{Beggining_firstline}-{protein_id} {End_firstline_str} product={product_name} "
                                make_bad_protein_len= open(bad_protein_len,'w', newline="")





                                #data for protein accessions and product names
                                processed_protein_rows.append([accession_ID, protein_id, product_name, note_in_gb, codon_start])
                                
                                sequence = feature.qualifiers["translation"][0] 
                                protein_tuple = (sequence)
                                seq_in_protein= len(protein_tuple)
                                #CDS number of nucleotides check
                                seq_in_nt= len(feature.location)
                                seq_test= seq_in_nt/3
                                if seq_test != seq_in_protein:
                                    len_match= "NO"
                                else:
                                    len_match= "YES"
                                len_report_writer = csv.writer(make_bad_protein_len, delimiter='\t')
                                len_report_writer.writerow(["Accession_ID",'Nucleotide_length','Protein_length','Match', "Protein_id"])
                                len_report_writer.writerow([accession_ID,seq_in_nt,seq_in_protein,len_match, protein_id])

                                make_bad_protein_len.close()
                               
                                
                                # Write to .faa
                                make_aa_file.write(f"{header}\n{sequence}\n")
                               
                        if args.verbose: print('    wrote: '+accession_aa_fasta, " with ", len(protein_check), " CDS records")
                else:
                    handle_accession_error(row, "no sequence found in {0}".format(accession_gb))
                    continue

    # output accession table, WITH fasta filenames
    Accessions["accession_gb"] = accession_gb_paths
    Accessions["accession_aa_fasta"] = accession_aa_fasta_paths
    Accessions["accession_nt_fasta"] = accession_nt_fasta_paths
    pd.DataFrame.to_csv(Accessions,processed_accessions_fanames_fname,sep='\t',index=False)
    print("Wrote to {0} rows, {1} columns to {2}".format(*Accessions.shape,processed_accessions_fanames_fname) )

    pd.DataFrame.from_records(processed_protein_rows, columns=processed_protein_columns).to_csv(
        processed_protein_accessions_fname, sep='\t', index=False
    )

    # wrap up and report errors
    print("Bad_Accession count:", len(bad_accessions))
    pd.DataFrame.from_records(bad_accessions, columns=Accessions.columns).to_csv(bad_accessions_fname,sep='\t',index=False)
    print("Wrote to ", bad_accessions_fname)

    
#######################################################################################################################################
# Calls makedatabase.sh. Uses 'all.fa'
#######################################################################################################################################
def make_database():
    if args.verbose: print("make_database()")
    p1 = subprocess.run("makedatabase.sh")
    
#######################################################################################################################################
# BLAST searches a given FASTA file and returns DataFrame rows with from the accession numbers. Returns in order of significance.  
#######################################################################################################################################
# How closely related
# Run 'A' viruses
# Compare to members of same species
# BLAST score -- 
# Top hit
# check to see if many seg return same virus

def query_database(path_to_query):
    results_dir="./results/e"
    results_file=results_dir+"/"+pathlib.Path(path_to_query).stem+".csv"

    if args.verbose: print("query_database("+path_to_query+")")
    if args.verbose: print("   run(query_database.sh "+path_to_query+" "+results_file)
    p1 = subprocess.run(["bash","query_database.sh",path_to_query,results_file])
    """
    if args.verbose: print("   reading: "+results_file")
    results = open(results_file,"r")
    result_text = results.readlines()
    results.close()
    print(res)
    """
    # set count to 20 since thats where result summary starts.
    """
    count = 20
    hits = []
    while True:
        current_line = result_text[count]
        count = count +1
        #checks to see if a "." is in the line and assumes from 20, it's an accession number. 
        if "." in current_line and ">" not in current_line:
            Accession_Number = current_line.split(" ")[0]
            Accession_Number = Accession_Number.split(".")[0]
            if args.verbose: print("  reading: "+processed_accesion_file_name)
            Isolates = pd.read_csv(processed_accession_file_name,sep='\t')
           
            hits = hits+[Isolates.loc[Isolates["Accession_IDs"] == Accession_Number]]
        elif ">" in current_line:
            break
    return hits 
    """

def main():
    if args.verbose: print("main()")

    if args.mode == "VMR" or None:
        print("# {0} load VMR".format(formatElapsedTime()))
        vmr_data = load_VMR_data()

        if args.verbose: print("# {0} testing accession IDs".format(formatElapsedTime()))
        tested_accessions_ids = test_accession_IDs(vmr_data)
        
        if args.verbose: print("Writing", processed_accession_file_name)
        if args.verbose: print("\tColumn: ", tested_accessions_ids.columns)
        pd.DataFrame.to_csv(tested_accessions_ids,processed_accession_file_name,sep='\t',index=False)

        bad_accessions_fname="./bad_accessions_"+args.ea.lower()+".tsv"
        accession_warning_rows = tested_accessions_ids.loc[
            tested_accessions_ids["Errors"].fillna("").astype(str).str.strip() != ""
        ]
        pd.DataFrame.to_csv(accession_warning_rows,bad_accessions_fname,sep='\t',index=False)

    if args.mode == "fasta" or None:
        print("# {0} pull FASTAs from NCBI".format(formatElapsedTime()))
        if args.verbose: print("Using ", processed_accession_file_name)
        fetch_fasta(processed_accession_file_name)

    if args.mode == "db" or None:
        print("# {0} Query local VMR-E BLASTdb".format(formatElapsedTime()))
        query_database(args.query)

main()

if args.verbose: print("# {0} Done.".format(formatElapsedTime()))





    
