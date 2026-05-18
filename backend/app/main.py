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
        return pd.read_csv(BytesIO(contents))

    if filename.endswith(".xlsx"):
        return pd.read_excel(BytesIO(contents))

    raise ValueError("Unsupported file type")


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

    return {
        "files_received": len(files),
        "rows": len(combined_df),
        "columns": list(combined_df.columns),
        "preview": combined_df.head(10).to_dict(orient="records"),
    }