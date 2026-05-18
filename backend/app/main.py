from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "DataCombiner backend is running"}00