import sys
import json
import time
import requests
from config import OLLAMA_HOST, MODEL_NAME, NUM_CTX
from context_manager import ContextManager

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def main():
    context = ContextManager()
    
    print("\n" + "="*50)
    print(" AI-Kane Node v2.5 (Metrics & Auto-Logs) Online")
    print(f" Target Model: {MODEL_NAME} | Hardware: RTX 3070 GPU")
    print("="*50 + "\n")
    print("Введите ваше сообщение (или 'выход' для завершения):\n")

    while True:
        try:
            raw_input = sys.stdin.buffer.readline()
            if not raw_input:
                break
                
            try:
                user_input = raw_input.decode('utf-8').strip()
            except UnicodeDecodeError:
                user_input = raw_input.decode('cp1251', errors='replace').strip()
            
            if user_input.lower() in ['exit', 'quit', 'выход']:
                context.save_history_to_disk()
                print("Завершение работы AI-Kane.")
                break
                
            if not user_input:
                continue

            context.add_message("user", user_input)
            
            payload = {
                "model": MODEL_NAME,
                "messages": context.get_context(),
                "stream": True,
                "options": {
                    "num_ctx": NUM_CTX,
                    "temperature": 0.3
                }
            }
            
            print("AI-Kane думает...", end="\r")
            
            # Фиксируем время отправки запроса
            start_time = time.perf_counter()
            
            response = requests.post(OLLAMA_HOST, json=payload, timeout=90, stream=True)
            response.raise_for_status()
            
            print("AI-Kane > ", end="", flush=True)
            
            full_ai_response = ""
            token_count = 0
            first_token_time = None
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        if json_str == "[DONE]":
                            break
                            
                        try:
                            data = json.loads(json_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                token = delta.get("content", "")
                                
                                if token:
                                    if first_token_time is None:
                                        # Замеряем время ответа первого токена (инференс)
                                        first_token_time = time.perf_counter() - start_time
                                        
                                    print(token, end="", flush=True)
                                    full_ai_response += token
                                    token_count += 1
                        except Exception:
                            continue
            
            # Фиксируем время окончания генерации
            end_time = time.perf_counter()
            total_generation_time = end_time - (start_time + (first_token_time or 0))
            
            print("\n")
            # Выводим блок аппаратных метрик скорости
            print("-" * 40)
            if token_count > 0 and total_generation_time > 0:
                tokens_per_sec = token_count / total_generation_time
                print(f" [Metrics] Speed: {tokens_per_sec:.2f} tokens/sec")
                print(f" [Metrics] Time to First Token: {first_token_time:.3f} sec")
            print("-" * 40 + "\n")
            
            context.add_message("assistant", full_ai_response)
            
        except (KeyboardInterrupt, EOFError):
            context.save_history_to_disk()
            print("\nЭкстренный выход. Данные сохранены.")
            break
        except Exception as e:
            print(f"\n[Ошибка API]: {e}\n")

if __name__ == "__main__":
    main()