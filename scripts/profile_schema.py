"""Print every sheet's shape, columns, dtypes, nulls and a few rows (reads work/ copies)."""

import sys

import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
for f in sys.argv[1:]:
    for name, df in pd.read_excel(f, sheet_name=None).items():
        print(f"\n##### {f.split('/')[-1]} :: {name}  shape={df.shape}")
        info = pd.DataFrame(
            {"dtype": df.dtypes.astype(str), "nulls": df.isna().sum(), "nunique": df.nunique()}
        )
        print(info.to_string())
        print(df.head(4).to_string())
