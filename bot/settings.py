"""Bot settings from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    allowlist_telegram_ids: str = ""
    max_queued_per_user: int = 3
    db_path: str = ""

    def allowed_ids(self) -> set[int]:
        if not self.allowlist_telegram_ids.strip():
            return set()
        return {int(x.strip()) for x in self.allowlist_telegram_ids.split(",") if x.strip()}
