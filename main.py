from fastapi import FastAPI
from app.routers.v1 import admin

app = FastAPI(title="E13-WASH API", version="1.0.0")

app.include_router(admin.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "ok", "project": "E13-WASH", "version": "1.0.0"}