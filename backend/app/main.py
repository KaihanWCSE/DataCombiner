from fastapi import FastAPI, UploadFile, File, Form
import pandas as pd
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "DataCombiner backend is running"}


def read_spreadsheet(filename: str, contents: bytes) -> pd.DataFrame:
    """
    Read one uploaded CSV/XLSX file into a normalized pandas DataFrame.
    For XLSX files, read the first sheet for now.
    """
    normalized_filename = filename.lower()

    if normalized_filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents))
    elif normalized_filename.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(contents))
    else:
        raise ValueError("Unsupported file type")

    return normalize_dataframe(df)


def normalize_text(value: str) -> str:
    """
    Normalize text by trimming whitespace and converting to lowercase.
    """
    return value.strip().lower()


def parse_merge_columns(merge_columns_json: str) -> list[str]:
    """
    Parse merge columns sent from the frontend as a JSON array string.
    Example frontend value: ["first name", "last name"]
    """
    try:
        raw_columns = json.loads(merge_columns_json)
    except json.JSONDecodeError:
        raise ValueError("merge_columns must be a JSON array")

    if not isinstance(raw_columns, list):
        raise ValueError("merge_columns must be a JSON array")

    merge_columns = []

    for column in raw_columns:
        if not isinstance(column, str):
            raise ValueError("Each merge column must be a string")

        normalized_column = normalize_text(column)

        if normalized_column and normalized_column not in merge_columns:
            merge_columns.append(normalized_column)

    if not merge_columns:
        raise ValueError("At least one merge column is required")

    return merge_columns


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

def mark_empty_source_values(
    df: pd.DataFrame,
    merge_columns: list[str],
) -> pd.DataFrame:
    """
    For rows that exist in a source file, mark empty non-merge cells as '?'.

    This preserves the distinction between:
    - person appeared in the source file but a value was blank -> '?'
    - person did not appear in the source file at all -> blank after merge
    """
    df = df.copy()
    merge_column_set = set(merge_columns)

    for column in df.columns:
        if column not in merge_column_set:
            df[column] = df[column].where(pd.notnull(df[column]), "?")

    return df

def prepare_file_for_merge(
    filename: str,
    df: pd.DataFrame,
    merge_columns: list[str],
    presence_column: str,
) -> pd.DataFrame:
    """
    Keep merge columns shared.
    Rename non-merge columns with their source filename.
    Keep internal presence marker unrenamed for appearance counting.
    """
    source_name = clean_source_name(filename)
    merge_column_set = set(merge_columns)

    renamed_columns = {}

    for column in df.columns:
        if column in merge_column_set or column == presence_column:
            continue

        renamed_columns[column] = f"{source_name} {column}"

    return df.rename(columns=renamed_columns)


async def combine_uploaded_files(
    files: list[UploadFile],
    merge_columns: list[str],
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Read, normalize, prepare, and merge uploaded files into one DataFrame.

    Attendance-roster behavior:
    - each uploaded file represents people who appeared/attended
    - appearance_count counts how many source files each merged person appeared in
    - blank values inside a source file become '?'
    - missing rows from a source file remain blank after merge
    """
    dataframes = []
    files_processed = []
    merge_column_set = set(merge_columns)
    presence_columns = []

    for index, file in enumerate(files):
        filename = file.filename
        contents = await file.read()

        df = read_spreadsheet(filename, contents)

        missing_merge_columns = merge_column_set - set(df.columns)
        if missing_merge_columns:
            raise ValueError(
                f"{filename} is missing merge column(s): {', '.join(sorted(missing_merge_columns))}"
            )

        presence_column = f"__present_source_{index}"
        presence_columns.append(presence_column)

        df = mark_empty_source_values(df, merge_columns)
        df[presence_column] = 1

        df = prepare_file_for_merge(
            filename=filename,
            df=df,
            merge_columns=merge_columns,
            presence_column=presence_column,
        )

        files_processed.append({
            "filename": filename,
            "rows": len(df),
            "columns": [
                column for column in df.columns
                if column != presence_column
            ],
        })

        dataframes.append(df)

    if not dataframes:
        raise ValueError("No files uploaded")

    combined_df = dataframes[0]

    for df in dataframes[1:]:
        combined_df = pd.merge(
            combined_df,
            df,
            on=merge_columns,
            how="outer",
        )

    combined_df["appearance_count"] = (
        combined_df[presence_columns]
        .fillna(0)
        .sum(axis=1)
        .astype(int)
    )

    combined_df = combined_df.drop(columns=presence_columns)

    ordered_columns = (
        merge_columns
        + ["appearance_count"]
        + [
            column for column in combined_df.columns
            if column not in merge_columns and column != "appearance_count"
        ]
    )

    combined_df = combined_df[ordered_columns]
    combined_df = combined_df.sort_values(by=merge_columns).reset_index(drop=True)

    return combined_df, files_processed

    if not dataframes:
        raise ValueError("No files uploaded")

    combined_df = dataframes[0]

    for df in dataframes[1:]:
        combined_df = pd.merge(
            combined_df,
            df,
            on=merge_columns,
            how="outer",
        )

    combined_df = combined_df.sort_values(by=merge_columns).reset_index(drop=True)

    return combined_df, files_processed


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


@app.post("/columns/common")
async def get_common_columns(
    files: Annotated[list[UploadFile], File(description="Upload multiple CSV/XLSX files")]
):
    """
    Return the columns shared by all uploaded files after normalization.
    """
    column_sets = []
    files_processed = []

    try:
        for file in files:
            filename = file.filename
            contents = await file.read()

            df = read_spreadsheet(filename, contents)
            columns = list(df.columns)

            column_sets.append(set(columns))
            files_processed.append({
                "filename": filename,
                "columns": columns,
            })
    except ValueError as error:
        return {"error": str(error)}

    if not column_sets:
        return {"error": "No files uploaded"}

    common_columns = set.intersection(*column_sets)

    return {
        "files_received": len(files),
        "files_processed": files_processed,
        "common_columns": sorted(common_columns),
    }


@app.post("/combine")
async def combine_files(
    files: Annotated[list[UploadFile], File(description="Upload multiple CSV/XLSX files")],
    merge_columns: Annotated[str, Form(description="JSON array of columns to merge files on")],
):
    try:
        selected_merge_columns = parse_merge_columns(merge_columns)
        combined_df, files_processed = await combine_uploaded_files(files, selected_merge_columns)
    except ValueError as error:
        return {"error": str(error)}

    preview_df = combined_df.head(10).astype(object)
    preview_df = preview_df.where(pd.notnull(preview_df), None)

    missing_values = combined_df.isna().sum().to_dict()

    return {
        "files_received": len(files),
        "files_processed": files_processed,
        "merge_columns": selected_merge_columns,
        "total_rows": len(combined_df),
        "columns": list(combined_df.columns),
        "missing_values": missing_values,
        "preview": preview_df.to_dict(orient="records"),
    }


@app.post("/combine/download")
async def download_combined_files(
    files: Annotated[list[UploadFile], File(description="Upload multiple CSV/XLSX files")],
    merge_columns: Annotated[str, Form(description="JSON array of columns to merge files on")],
):
    try:
        selected_merge_columns = parse_merge_columns(merge_columns)
        combined_df, _ = await combine_uploaded_files(files, selected_merge_columns)
    except ValueError as error:
        return {"error": str(error)}

    csv_buffer = io.StringIO()
    combined_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=combined.csv"
        },
    )