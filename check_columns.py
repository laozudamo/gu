import akshare as ak
import pandas as pd

try:
    print("Fetching one page of data...")
    df = ak.stock_zh_a_spot_em()
    print("Columns:", df.columns.tolist())
    
    # Check for share capital related columns
    potential_cols = [c for c in df.columns if '股本' in c or '总市值' in c or '流通市值' in c]
    print("Relevant Columns:", potential_cols)
    
    if not df.empty:
        sample = df.iloc[0]
        print("\nSample Data:")
        for c in potential_cols:
            print(f"{c}: {sample[c]}")
            
except Exception as e:
    print(e)
