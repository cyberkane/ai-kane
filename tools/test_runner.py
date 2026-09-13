import sys
import subprocess
import asyncio
from metrics.telemetry import log_event

def _run_pytest_sync(module_path: str) -> tuple[int, str, str]:
    """Синхронный воркер для выполнения тестов в изолированном потоке"""
    cmd = [sys.executable, "-m", "pytest", "-v", module_path]
    
    # Запускаем через стандартный subprocess, так как мы уже внутри отдельного потока
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
    return result.returncode, result.stdout, result.stderr


async def run_project_tests(module_path: str = "tests") -> str:
    """Запускает pytest без блокировки сервера, используя пул потоков (Thread Pool)."""
    if not module_path or module_path in ["None", "{}", ""]:
        module_path = "tests"
        
    log_event(
        body=f"Executing tool: run_project_tests for path '{module_path}'", 
        event_name="tool_test_runner_start",
        attributes={"path": module_path}
    )
    
    try:
        # ИСПРАВЛЕНО: asyncio.to_thread переносит блокирующую задачу в фоновый поток.
        # Это полностью решает проблему NotImplementedError на Windows!
        return_code, stdout, stderr = await asyncio.to_thread(_run_pytest_sync, module_path)
        
        status_line = "✅ Тесты успешно пройдены!" if return_code == 0 else "❌ Обнаружены упавшие тестов!"
        
        log_event(
            body=f"Project tests completed with code {return_code}",
            event_name="tool_test_runner_end",
            attributes={"return_code": return_code, "status": "success" if return_code == 0 else "warning"}
        )
        return f"📋 [Test Runner] Статус: {status_line}\n\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        
    except asyncio.TimeoutError:
        return "⚠️ [Test Runner] Превышен таймаут выполнения тестов (30 секунд)."
    except Exception as e:
        return f"❌ [Test Runner] Критическая ошибка при выполнении тестов: {type(e).__name__} -> {str(e)}"
