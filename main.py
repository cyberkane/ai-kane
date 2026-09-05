import sys
import requests
from config import OLLAMA_HOST, MODEL_NAME, NUM_CTX
from context_manager import ContextManager

# Защита от багов кодировки консоли Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def main():
    context = ContextManager()
    
    print("\n" + "="*50)
    print(" AI-Kane Node (Alpine Base) Online")
    print(f" Target Model: {MODEL_NAME}")
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
                "options": {
                    "num_ctx": NUM_CTX,
                    "temperature": 0.3
                }
            }
            
            print("AI-Kane думает...", end="\r")
            
            response = requests.post(OLLAMA_HOST, json=payload, timeout=90)
            response.raise_for_status()
            
            response.encoding = 'utf-8' 
            data = response.json()
            
            # Проверяем, вернул ли сервер ошибку в JSON
            if "error" in data:
                print(f"\n[Ошибка Ollama]: {data['error']}")
                continue
                
            # ИСПРАВЛЕНО: Добавлен индекс [0] для выбора первого ответа из списка choices
            ai_response = data['choices'][0]['message']['content']
            
            context.add_message("assistant", ai_response)
            
            print(f"AI-Kane > {ai_response}\n")
            
        except (KeyboardInterrupt, EOFError):
            context.save_history_to_disk()
            print("\nЭкстренный выход. Данные сохранены.")
            break
        except Exception as e:
            print(f"\n[Ошибка API]: {e}\n")

if __name__ == "__main__":
    main()