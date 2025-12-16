#!/usr/bin/env python3
#
# test Pandas DataTAble subsetting
#

import pandas as pd
import numpy as py

#
# load data
#
df = pd.read_csv("data.csv")

print("""
#
# subset: Query
#
""")

hits1 = df.query('Duration==60 & Pulse==117')
print(hits1)

print("""
#
# subset: Query (parameterized)
#
""")

dur=60
pul=117
hits1p = df.query('Duration==@dur & Pulse==@pul')
print(hits1p)

print("""
#
# subset: Boolean
#
""")

hits2 = df[(df['Duration']==60) & (df['Pulse']==117)]
print(hits2)
      
