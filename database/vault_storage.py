# -*- coding: utf-8 -*-
import os
import httpx
from metrics.telemetry import log_event

def get_vault_config() -> tuple[str, str]:
    """
    Динамически извлекает адрес Vault и токен авторизации из глобального app_config.
    Учитывает запуск вне Docker-сети (на локальном хосте Windows).
    """
    from main import app_config
    
    vault_cfg = app_config.get("vault", {})
    host = vault_cfg.get("host", "http://localhost")
    port = vault_cfg.get("port", "8200")
    token = vault_cfg.get("token", "")
    
    # Умная подмена хоста: если в конфиге имя контейнера 'vault' 
    # или 'ai_vault_core', а мы запускаем код локально — шлем запросы на localhost
    if ("vault" in host or "ai_vault_core" in host) and not os.path.exists("/.dockerenv"):
        host = "http://localhost"
        
    return f"{host}:{port}", token


async def fetch_database_secrets() -> dict:
    """
    Полностью асинхронно запрашивает секреты InfluxDB из KV-2 хранилища Vault.
    Защищает приложение от утечки открытых паролей в файлах конфигурации.
    """
    vault_url, vault_token = get_vault_config()
    
    log_event(
        body="Fetching database credentials from HashiCorp Vault API", 
        event_name="vault_fetch_start"
    )
    
    # URL для чтения данных из KV Version 2 движка Vault: /v1/{mount}/data/{path}
    secret_url = f"{vault_url}/v1/secret/data/marmai/database"
    headers = {
        "X-Vault-Token": vault_token,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(secret_url, headers=headers, timeout=5.0)
            
            if response.status_code == 403:
                print("❌ === [Vault] Ошибка 403: Токен авторизации отклонен Vault! ===")
                return {}
            elif response.status_code == 404:
                print("⚠️ === [Vault] Ошибка 404: Секреты по пути secret/marmai/database не найдены ===")
                return {}
            elif response.status_code != 200:
                print(f"⚠️ === [Vault] Нетипичный ответ от Vault. Статус: {response.status_code} ===")
                return {}
                
            payload = response.json()
            # По спецификации Vault KV-2 данные лежат внутри ключа data -> data
            secrets_data = payload.get("data", {}).get("data", {})
            
            log_event(
                body="Successfully retrieved and decrypted database credentials from Vault",
                event_name="vault_fetch_success",
                attributes={"status": "success"}
            )
            return secrets_data
            
    except (httpx.ConnectError, httpx.ConnectTimeout) as net_err:
        print(f"❌ === [Vault] Сервер Vault недоступен по адресу {vault_url}. Ошибка: {net_err} ===")
        return {}
    except Exception as e:
        print(f"❌ === [Vault] Критическая ошибка при работе с Vault: {e} ===")
        return {}