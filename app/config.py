import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # --- CẤU HÌNH CHUNG ---
    APP_NAME: str = "Suncloud Management API"
    VERSION: str = "1.0.0"
    ENV: str = Field("development", env="APP_ENV")

    # --- CẤU HÌNH NETBOX ---
    NETBOX_URL: str = Field("http://172.16.66.82:32080", env="NETBOX_URL")
    NETBOX_TOKEN: str = Field(..., env="NETBOX_TOKEN") # Không để default, bắt buộc phải có trong .env hoặc K8s Secret
    NETBOX_SSL_VERIFY: bool = Field(False, env="NETBOX_SSL_VERIFY")

    # --- CẤU HÌNH MYSQL ---
    MYSQL_HOST: str = Field("mysql-service", env="MYSQL_HOST")
    MYSQL_PORT: int = Field(3306, env="MYSQL_PORT")
    MYSQL_USER: str = Field("admin", env="MYSQL_USER")
    MYSQL_PASSWORD: str = Field("Suncloud@2026!", env="MYSQL_PASSWORD")
    MYSQL_DATABASE: str = Field("app_database", env="MYSQL_DATABASE")

    # --- CẤU HÌNH BẢO MẬT (JWT AUTH) ---
    SECRET_KEY: str = Field("super-secret-fastapi-key-2026", env="SECRET_KEY")
    ALGORITHM: str = Field("HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # Định nghĩa cấu hình nạp file .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Bỏ qua nếu trong .env có các biến thừa khác
    )

    @property
    def database_url(self) -> str:
        """Tự động tạo chuỗi Connection String cho SQLAlchemy an toàn với ký tự đặc biệt"""
        encoded_password = quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

# Khởi tạo một object duy nhất để toàn bộ hệ thống import sử dụng
settings = Settings()