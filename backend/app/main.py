from fastapi import FastAPI, UploadFile, File
import pandas as pd
from io import BytesIO

app = FastAPI()


@app.get("/")
def root():
    return {"message": "DataCombiner backend is running"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename

    # Read uploaded file bytes first.
    # This is more reliable than passing file.file directly to pandas.
    contents = await file.read()

    if filename.endswith(".csv"):
        df = pd.read_csv(BytesIO(contents))

        return {
            "filename": filename,
            "rows": len(df),
            "columns": list(df.columns),
            "preview": df.head(5).to_dict(orient="records"),
        }

    elif filename.endswith(".xlsx"):
        excel_file = pd.ExcelFile(BytesIO(contents))

        sheets_info = {}

        for sheet_name in excel_file.sheet_names:
            sheet_df = pd.read_excel(
                BytesIO(contents),
                sheet_name=sheet_name
            )

            sheets_info[sheet_name] = {
                "rows": len(sheet_df),
                "columns": list(sheet_df.columns),
                "preview": sheet_df.head(5).to_dict(orient="records"),
            }

        return {
            "filename": filename,
            "sheets": sheets_info,
        }

    else:
        return {"error": "Unsupported file type"}