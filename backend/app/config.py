from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_root: Path | None = None
    data_dir: str = "ws_demand_dataset"
    ws_model_dir: str = "ws_model"
    ml_ready_file: str = "ml_ready_data.csv"
    influencer_model_dir: str = "models"
    features_engineered_file: str = "features_engineered.csv"
    analytics_dir: str = "analytics"
    case_study_data_dir: str = "data"
    conti_model_dir: str = "models"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    def root(self) -> Path:
        if self.project_root is not None:
            return Path(self.project_root).resolve()
        return _default_project_root()

    def ml_ready_path(self) -> Path:
        return self.root() / self.data_dir / self.ml_ready_file

    def demand_predictions_path(self) -> Path:
        return self.root() / self.analytics_dir / "demand_with_predictions.csv"

    def sales_timeseries_path(self) -> Path:
        return self.root() / self.analytics_dir / "sales_timeseries.csv"

    def inventory_path(self) -> Path:
        return self.root() / self.case_study_data_dir / "inventory.csv"

    def signals_path(self) -> Path:
        return self.root() / self.case_study_data_dir / "signals.csv"

    def best_model_path(self) -> Path:
        return self.root() / self.ws_model_dir / "best_model.pkl"

    def feature_cols_path(self) -> Path:
        return self.root() / self.ws_model_dir / "feature_cols.pkl"

    def features_engineered_path(self) -> Path:
        return self.root() / self.features_engineered_file

    def influencer_metrics_path(self) -> Path:
        return self.root() / self.analytics_dir / "influencer_metrics.json"

    def influencer_sample_path(self) -> Path:
        return self.root() / self.analytics_dir / "influencer_sample.csv"

    def conti_model_path(self) -> Path:
        return self.root() / self.conti_model_dir / "conti_model.pkl"

    def conti_features_path(self) -> Path:
        return self.root() / self.conti_model_dir / "conti_features.json"

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
