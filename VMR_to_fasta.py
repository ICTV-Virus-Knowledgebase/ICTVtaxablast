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
args = parser.parse_args()
if args.mode != 'fasta' and args.mode != "VMR" and args.mode != "db":
    print("Valid mode not selected. Options: VMR,fasta,db",file=sys.stderr)
#Takes forever to import so only imports if it's going to be needed
if args.mode == 'fasta':
    print("Importing Entrez from Bio...")
    from Bio import Entrez
#Catching error
if args.mode == "db":
    if args.query == None:
        print("Database Query mode is selected but no fasta file was specified! Please set the '-fasta_file_name' or change mode.",file=sys.stderr)

VMR_file_name_tsv = './vmr.tsv'
VMR_hack_file_name = "./fixed_vmr_"+args.ea.lower()+".tsv"
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
    if args.ea.upper() == 'A' or args.ea.upper() == 'E': 
        vmr_data = raw_vmr_data.loc[raw_vmr_data['Exemplar or additional isolate']==args.ea.upper(),vmr_cols_needed]
    elif args.ea.upper() == 'B':
        # both e and a
        vmr_data = raw_vmr_data.loc[raw_vmr_data['Exemplar or additional isolate']!='',vmr_cols_needed]

    # only works when I reload the vmr_data, probably not necessary. have to look into why it's doing this. 
    if args.verbose: print("Writing"+VMR_hack_file_name,": workaround - filters VMR down to "+args.ea.upper()+" records only")
    if args.verbose: print("\tcolumns: ",vmr_data.columns)
    
    vmr_data.to_csv(VMR_hack_file_name, sep='\t')
    if args.verbose: print("Loading",VMR_hack_file_name)
    narrow_vmr_data = pd.read_csv(VMR_hack_file_name,sep='\t')
    if args.verbose: print("   Read {0} rows, {1} columns.".format(*narrow_vmr_data.shape))
    if args.verbose: print("   columns:", list(narrow_vmr_data.columns))

    if args.verbose: print("   Truncated: {0} rows, {1} columns.".format(*narrow_vmr_data.shape))
    
    return narrow_vmr_data

#insert(parse_seg_accession_list)
def parse_seg_accession_list(isolate_id,acc_list_str):
    # remove whitespace.
    acc_list_str = acc_list_str.replace(" ","")

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
                accession = seg_acc_pair[0]
                result_arr.append({"accession":accession, "segment_name":None, "accession_index":accession_index, "isolate_id":isolate_id})
                if args.tmi: print("result_arr["+str(accession_index)+"]:"+str(result_arr[accession_index-1]))
            elif len(seg_acc_pair)==2:
                # seg_name:accession
                segment_name = seg_acc_pair[0]
                accession = seg_acc_pair[1]
                result_arr.append({"accession":accession, "segment_name":segment_name, "accession_index":accession_index, "isolate_id":isolate_id})
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
    # defining new DataFrame before hand
    processed_accessions = pd.DataFrame(columns=[
        'ICTV_ID','Isolate_ID','Exemplar_Additional','Accession_Index','Segment_Name','Accession', # 0-5
        'Start_Loc','End_Loc','Sort','Isolate_Sort','Original_GENBANK_Accessions','Errors', # 6-11
        'Realm','Subrealm','Kingdom','Subkingdom','Phylum','Subphylum','Class','Subclass','Order','Suborder', # 12-21
        'Family','Subfamily','Genus','Subgenus','Species','Virus_Names' # 22-27
    ])
    # pattern for accessions qualified by "(START,STOP)" subsequence qualifiers
    accession_start_end_regex = r'(\w+)\s*\((\d+)(\.)(\w+)(\))'

    # for loop for every entry in given processed_accessionIDs
    for entry_count in range(0,len(df.index)):
        #
        # split accessions list (seporarated by ;  by , )
        #
        
        isolate_id_str = str(df['Isolate ID'][entry_count])
        # get original list of accessions
        gb_accessions_str = str(df['Virus GENBANK accession'][entry_count])
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
            re_result=re.match(accession_start_end_regex, acc_dict['accession'])

            if re_result:
                # accession is qualified - parse out accession from START/STOP nt coords
                processed_accession= re_result.group(1)
                start_loc= re_result.group(2)
                end_loc  = re_result.group(4)
            else:
                # use accession as is
                processed_accession = acc_dict['accession']
                
            processed_accessions.loc[len(processed_accessions.index)] = [
                # 0-5
                df['ICTV_ID'][entry_count], 
                df['Isolate ID'][entry_count],
                df['Exemplar or additional isolate'][entry_count],
                acc_dict['accession_index'],
                acc_dict['segment_name'],
                processed_accession,
                # 6-11
                start_loc,
                end_loc,
                df['Species Sort'][entry_count],
                df['Isolate Sort'][entry_count],
                df['Virus GENBANK accession'][entry_count],
                '', # errors
                # 12-21
                df['Realm'][entry_count],
                df['Subrealm'][entry_count],
                df['Kingdom'][entry_count],
                df['Subkingdom'][entry_count],
                df['Phylum'][entry_count],
                df['Subphylum'][entry_count],
                df['Class'][entry_count],
                df['Subclass'][entry_count],
                df['Order'][entry_count],
                df['Suborder'][entry_count],
                # 22-27
                df['Family'][entry_count],
                df['Subfamily'][entry_count],
                df['Genus'][entry_count],
                df['Subgenus'][entry_count],
                df['Species'][entry_count],
                df['Virus name(s)'][entry_count],
            ]
            #print("'"+processed_accession+"'"+' has been cleaned.')

    return processed_accessions

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

    bad_accessions_fname="./bad_accessions_"+args.ea.lower()+".tsv"
    processed_accessions_fanames_fname=processed_accession_file_name.replace(".tsv","")+".fa_names.tsv"

    #Check to see if fasta data exists and, if it does, loads the accessions numbers from it into an np array.
    if args.verbose: print("  loading:", processed_accession_file_name)
    Accessions = pd.read_csv(processed_accession_file_name,sep='\t')

    all_reads = []
    bad_accessions = pd.DataFrame(columns=Accessions.columns)

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

    # Fetches FASTA data for every accession number
    count = 0
    for accession_ID in Accessions['Accession']:
            row = Accessions.loc[count]
            Isolate_ID   = row.iloc[1]
            Isolate_type = row.iloc[2]
            segment      = row.iloc[4]
            # accession_ID = row.iloc[6]
            family_name  = row.iloc[22]
            genus_name   = row.iloc[24]
            species_name = row.iloc[26]
            virus_names  = row.iloc[27]
            if args.verbose: print("Fetch [",count,"] ID:",Isolate_ID," Species:",species_name," Segment:",segment," Accession:",accession_ID)

            # emtpy cell becomes float:NaN!
            if segment != segment:         segment = ""
            if genus_name != genus_name:   genus_name = ""
            if family_name != family_name: family_name = ""
                
            # fasta_file_name
            genus_dir = args.fasta_dir+"/"+str(genus_name)
            if genus_name == "":
                genus_dir = args.fasta_dir+"/"+"no_genus"
            accession_raw_file_name = genus_dir+"/"+str(accession_ID)+".raw"
            accession_fa_file_name = genus_dir+"/"+str(accession_ID)+".fa"
            
            # Assign the computed values to the new columns
            Accessions.loc[count, "accession_raw_file_name"] = accession_raw_file_name
            Accessions.loc[count, "accession_fa_file_name"] = accession_fa_file_name
    
            # make sure dir exists
            if not os.path.exists(genus_dir):
                # Create the directory if it doesn't exist
                os.makedirs(genus_dir)
                if args.verbose: print(f"Directory '{genus_dir}' created successfully.")
    
            # check if the raw file exists
            if os.path.exists(accession_raw_file_name):
                if args.verbose: print("[FETCH]  SKIP NCBI fetch for {accession_raw_file_name}".format(**locals()))
            else:
                raw_file = open(accession_raw_file_name,'w')
                if args.verbose: print("[FETCH]  EXEC NCBI fetch for {accession_raw_file_name}".format(**locals()))
                try:
                    # fetch FASTA from NCBI
                    handle = Entrez.efetch(db="nuccore", id=accession_ID, rettype="fasta", retmode="text")

                    # limit requests: 3/second with email, 10/second with API_KEY
                    time.sleep(entrez_sleep)

                    # prints out accession that got though cleaning
                    if args.verbose: print('    fasta for '+accession_ID+ ' obtained.')

                    # prints out accession that got though cleaning
                    raw_fa = handle.read()
                    raw_file.write(raw_fa);
                    raw_file.close()
                    if args.verbose: print('    wrote: '+accession_raw_file_name)

                except:
                    print("    [ERR] Accession ID "+"'"+str(accession_ID)+"'"+" Entrez.efetch threw an error",file=sys.stderr)
                    bad_accessions = pd.concat([bad_accessions, pd.DataFrame([row])], ignore_index=True)

            # check if processed fasta is out of date
            if os.path.getsize(accession_raw_file_name) == 0:
                if args.verbose: print("[FORMAT] SKIP/ERROR raw files is empty for {accession_fa_file_name}".format(**locals()))
            elif os.path.exists(accession_fa_file_name) and os.path.getmtime(accession_fa_file_name) > os.path.getmtime(accession_raw_file_name):
                if args.verbose: print("[FORMAT] SKIP reformat header for {accession_fa_file_name}".format(**locals()))
            else:
                if args.verbose: print("[FORMAT] EXEC reformat header for {accession_fa_file_name}".format(**locals()))
                
                # open local raw genbank fasta
                raw_file = open(accession_raw_file_name,'r')
                raw_fa = raw_file.read()
                raw_file.close()

                # open local (header modified) version
                fa_file  = open(accession_fa_file_name,'w')

                # parse out header and seq
                fa_desc = raw_fa.split("\n")[0].replace(">","")
                ncbi_accession = fa_desc.split(" ",1)[0]
                fa_seq =    raw_fa.split("\n",1)[1]

                # build ICTV-modified header
                #  ACCESSION#VMR_SPECIES[#VMR_SEG] FAMILY TYPE VMR_ID ISOLATE_NAME 

                #field_sep="#"
                field_sep="-"
                # remove spaces and field separators
                species_name_cleaned = str(  species_name).replace(" ","_").replace("-","_")
                segment_cleaned =      str(       segment).replace(" ","_").replace("-","_")
                accession_cleaned =    str(ncbi_accession)
                if str(segment).lower() == "":
                    # leave out #SEG
                    #desc_line = '>'+field_sep.join([str(ncbi_accession),str(species_name.replace(" ","_"))])
                    desc_line = '>'+field_sep.join([species_name_cleaned,"",accession_cleaned])
                else:
                    # include #SEG
                    #desc_line = '>'+'#'.join([str(ncbi_accession),str(species_name.replace(" ","_")),str(segment)])
                    desc_line = '>'+field_sep.join([species_name_cleaned,segment_cleaned,accession_cleaned])
                # add comments to fasta header
                #desc_line = ' '.join([desc_line,family_name,Isolate_type,Isolate_ID,virus_names])
                desc_line = ' '.join([desc_line,family_name,Isolate_type,virus_names])
                
                if args.verbose: print("    ", desc_line)

                # write ICTV formated header to fasta
                fa_file.write(desc_line+"\n"+fa_seq)
                fa_file.close()
                if args.verbose: print('    wrote: '+accession_fa_file_name)
                
            count=count+1

    # output accession table, WITH fasta filenames
    pd.DataFrame.to_csv(Accessions,processed_accessions_fanames_fname,sep='\t')
    print("Wrote to {0} rows, {1} columns to {2}".format(*Accessions.shape,processed_accessions_fanames_fname) )

    # wrap up and report errors
    print("Bad_Accession count:", len(bad_accessions.index))
    pd.DataFrame.to_csv(bad_accessions,bad_accessions_fname,sep='\t')
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

    if args.mode == "fasta" or None:
        print("# {0} pull FASTAs from NCBI".format(formatElapsedTime()))
        if args.verbose: print("Using ", processed_accession_file_name)
        fetch_fasta(processed_accession_file_name)

    if args.mode == "db" or None:
        print("# {0} Query local VMR-E BLASTdb".format(formatElapsedTime()))
        query_database(args.query)

main()

if args.verbose: print("# {0} Done.".format(formatElapsedTime()))





    






