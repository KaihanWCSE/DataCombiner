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
    Read one uploaded CSV/XLSX file into a normalized pandas DataFrame.
    For XLSX files, read the first sheet for now.
    """
    if filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(contents))
    elif filename.endswith(".xlsx"):
        df = pd.read_excel(BytesIO(contents))
    else:
        raise ValueError("Unsupported file type")

    return normalize_dataframe(df)

def normalize_text(value: str) -> str:
    """
    Normalize text by trimming whitespace and converting to lowercase.
    """
    return value.strip().lower()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize all column names and all string cell values.
    """
    df = df.copy()

    df.columns = [normalize_text(str(column)) for column in df.columns]
    df = df.map(lambda value: normalize_text(value) if isinstance(value, str) else value)

    return df


def clean_source_name(filename: str) -> str:
    """
    Convert a source filename like Book1.xlsx into book1.
    Used only for source-specific column names.
    """
    name_without_extension = filename.rsplit(".", 1)[0]
    return normalize_text(name_without_extension)


def prepare_file_for_merge(
    filename: str,
    df: pd.DataFrame,
    merge_columns: set[str],
) -> pd.DataFrame:
    """
    Keep merge columns shared.
    Rename non-merge columns with their source filename.
    """
    source_name = clean_source_name(filename)

    renamed_columns = {}

    for column in df.columns:
        if column not in merge_columns:
            renamed_columns[column] = f"{source_name} {column}"

    return df.rename(columns=renamed_columns)


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
    files_processed = []

    # Temporary hardcoded user choice.
    # Later, the frontend will ask the user whether each duplicate column
    # should be merged or kept separate.
    merge_columns = {"names"}

    for file in files:
        filename = file.filename
        contents = await file.read()

        try:
            df = read_spreadsheet(filename, contents)
            df = prepare_file_for_merge(filename, df, merge_columns)
        except ValueError as error:
            return {
                "filename": filename,
                "error": str(error),
            }

        files_processed.append({
            "filename": filename,
            "rows": len(df),
            "columns": list(df.columns),
        })

        dataframes.append(df)

    if not dataframes:
        return {"error": "No files uploaded"}

    combined_df = dataframes[0]

    for df in dataframes[1:]:
        combined_df = pd.merge(
            combined_df,
            df,
            on=list(merge_columns),
            how="outer",
        )

    combined_df = combined_df.sort_values(by=list(merge_columns)).reset_index(drop=True)

    preview_df = combined_df.head(10).astype(object)
    preview_df = preview_df.where(pd.notnull(preview_df), None)

    missing_values = combined_df.isna().sum().to_dict()

    return {
        "files_received": len(files),
        "files_processed": files_processed,
        "merge_columns": list(merge_columns),
        "total_rows": len(combined_df),
        "columns": list(combined_df.columns),
        "missing_values": missing_values,
        "preview": preview_df.to_dict(orient="records"),
    }