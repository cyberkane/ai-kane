import os
import hvac

def get_vault_secrets(logger):
    VAULT_URL = os.getenv("VAULT_URL", "http://ai_vault_core:8200")
    VAULT_TOKEN = os.getenv("VAULT_MASTER_TOKEN")

    logger.info("Инициализация подключения к HashiCorp Vault", extra={"vault.url": VAULT_URL})

    client = hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)

    if not client.is_authenticated():
        logger.error("Критическая ошибка: Не удалось авторизоваться в Vault!")
        raise Exception("Vault authentication failed")

    try:
        # Читаем секрет
        secret_response = client.secrets.kv.v2.read_secret_version(
            mount_point="secret",
            path="influxdb",
            raise_on_deleted_version=True
        )
        influx_secrets = secret_response["data"]["data"]
        
        # Логируем успешное событие (⚠️ Безопасно: НЕ выводим сами пароли/токены в лог!)
        logger.info(
            "Конфигурация InfluxDB успешно загружена из Vault", 
            extra={
                "influx.db": influx_secrets.get("database"),
                "influx.user": influx_secrets.get("bootstrap_user"),
                "influx.org": influx_secrets.get("org")
            }
        )
        
        return influx_secrets

    except Exception as e:
        logger.error("Ошибка при получении секретов из Vault", extra={"error.message": str(e)})
        raise e