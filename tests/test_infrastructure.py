import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_environment_variables():
    """Проверяем, что критические переменные окружения подгрузились в контейнер."""
    assert os.getenv("VAULT_MASTER_TOKEN") is not None
    # 🔄 Проверяем то имя, которое реально проброшено
    assert os.getenv("INFLUX_BOOTSTRAP_TOKEN") is not None or os.getenv("INFLUXDB_TOKEN") is not None
    assert os.getenv("MINIO_SECRET_KEY") == "marmadmin"

def test_analytics_import():
    """Проверяем, что кристаллическая решётка импортов аналитики не сломана."""
    try:
        import analytics
        print("🟢 Модуль analytics успешно обнаружен!")
        assert True
    except Exception as e:
        pytest.fail(f"Критическая ошибка: модуль analytics не может быть импортирован. Ошибка: {e}")
