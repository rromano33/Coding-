"""Run this locally (no Bloomberg needed) to print the real layout of
Inputs_BCs.xlsx, then paste the output back so excel_loader.py's column
mapping in config/settings.yaml can be corrected to match.

Usage: python scripts/inspect_inputs.py "C:\\Users\\RRZBCSH\\Projects\\meu-projeto\\Data\\Inputs_BCs.xlsx"
"""
import sys

import pandas as pd


def main(path: str) -> None:
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, nrows=5)
        print(f"\n=== {sheet} ===")
        print("columns:", list(df.columns))
        print(df.to_string())


if __name__ == "__main__":
    default_path = r"C:\Users\RRZBCSH\Projects\meu-projeto\Data\Inputs_BCs.xlsx"
    main(sys.argv[1] if len(sys.argv) > 1 else default_path)
