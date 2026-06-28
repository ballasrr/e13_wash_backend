from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # CrestWave
    CRESTWAVE_TOKEN: str
    CRESTWAVE_BASE_URL: str
    # PostgreSQL
    POSTGRES_URL: str
    # ClickHouse
    CLICKHOUSE_HOST: str
    CLICKHOUSE_PORT: int
    CLICKHOUSE_DB: str
    CLICKHOUSE_USER: str
    CLICKHOUSE_PASSWORD: str
    # Redis
    REDIS_URL: str

settings = Settings()