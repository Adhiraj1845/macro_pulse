from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    fred_api_key: str = ""
    database_url: str = "sqlite:///./macro_api.db"
    app_title: str = "Macro & Market Impact Analytics API"
    app_version: str = "1.0.0"
    app_description: str = (
        "A REST API for tracking macroeconomic indicators and financial market assets, "
        "with analytical endpoints for correlation analysis, recession risk scoring, "
        "sector impact analysis, and macro trend detection."
    )

    class Config:
        env_file = ".env"


settings = Settings()
