from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.clickhouse import init_clickhouse
from app.routers.v1 import admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_clickhouse()
    yield


app = FastAPI(
    title="E13-WASH API",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(admin.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"status": "ok", "project": "E13-WASH", "version": "1.0.0"}