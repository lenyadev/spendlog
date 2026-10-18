from spendlog.core.config import get_settings

def test_settings_load() -> None:
    settings = get_settings()

    assert settings.app_env == "development"
    assert settings.app_name == "Spendlog"
    assert settings.jwt_algorithm == "HS256"