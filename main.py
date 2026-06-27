from fastapi import FastAPI

app = FastAPI(title="E13-WASH API", version="1.0.0")


@app.get("/")
async def root():
    return {"status": "ok", "project": "E13-WASH", "version": "1.0.0"}