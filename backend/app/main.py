from fastapi import FastAPI, UploadFile, File
import pandas as pd
from io import BytesIO
from typing import Annotated

app = FastAPI()


@app.get("/")
def root():
    return {"message": "DataCombiner backend is running"}


def read_spreadsheet(filename: str, contents: bytes) -> pd.DataFrame:
    """
    Read one uploaded CSV/XLSX file into a pandas DataFrame.
    For XLSX files, read the first sheet for now.
    """
    if filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(contents))
    elif filename.endswith(".xlsx"):
        df = pd.read_excel(BytesIO(contents))
    else:
        raise ValueError("Unsupported file type")

    df.columns = df.columns.str.strip().str.lower()
    df = df.apply(lambda col: col.str.strip().str.lower() if col.dtype == "object" else col)

    return df


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename
    contents = await file.read()

    try:
        df = read_spreadsheet(filename, contents)
    except ValueError as error:
        return {"error": str(error)}

    return {
        "filename": filename,
        "rows": len(df),
        "columns": list(df.columns),
        "preview": df.head(5).to_dict(orient="records"),
    }


@app.post("/combine")
async def combine_files(
    files: Annotated[list[UploadFile], File(description="Upload multiple CSV/XLSX files")]
):
    dataframes = []

    for file in files:
        filename = file.filename
        contents = await file.read()

        try:
            df = read_spreadsheet(filename, contents)
        except ValueError as error:
            return {
                "filename": filename,
                "error": str(error),
            }

        df["source_file"] = filename
        dataframes.append(df)

    if not dataframes:
        return {"error": "No files uploaded"}

    combined_df = pd.concat(dataframes, ignore_index=True)

    preview_df = combined_df.head(10).astype(object)
    preview_df = preview_df.where(pd.notnull(preview_df), None)

    duplicate_rows = int(combined_df.drop(columns=["source_file"]).duplicated().sum())
    missing_values = combined_df.isna().sum().to_dict()

    return {
        "files_received": len(files),
        "total_rows": len(combined_df),
        "columns": list(combined_df.columns),
        "duplicate_rows": duplicate_rows,
        "missing_values": missing_values,
        "preview": preview_df.to_dict(orient="records"),
    }