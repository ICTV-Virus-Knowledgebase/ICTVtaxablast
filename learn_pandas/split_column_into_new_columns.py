#!/usr/bin/env python3
#
# code from ChatGPT4, prompt
#

# write a python code snippet to split the string values at each occurrence of a "#",
# in the 'sseqid' column of a pandas dataframe and place the first 3 values for each row
# into the new columns 'saccession', 'sspecies', 'sseg', respectively.
# If there is no 3rd value, then use the empty string, "".
#


import pandas as pd
from pprint import pprint        

# Example DataFrame
data = {'sseqid': ['value1#value2#value3', 'value4#value5', 'value6#value7#value8#value9']}
#data = {'sseqid': ['value1#value2', 'value4#value5', 'value6']}
print("# data=")
pprint(data)
df = pd.DataFrame(data)

# Splitting the string values and creating new columns
split_values = df['sseqid'].str.split('#', expand=True)
print("type(split_values):",type(split_values))
print("shape(split_values):",split_values.shape)
if split_values.shape[1] < 3:
    print("3rd column missing in split values, adding it")
    split_values[2] = ""
pprint(split_values)
df['saccession'] = split_values[0]
df['sspecies'] = split_values[1]
df['sseg'] = split_values[2].fillna("")

# Displaying the updated DataFrame
print(df)
