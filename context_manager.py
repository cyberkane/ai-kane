import json
import os
from config import load_system_prompt, MAX_HISTORY_LEN

class ContextManager:
    def __init__(self):
        # Инициализируем историю с системного промпта
        self.history = [{"role": "system", "content": load_system_prompt()}]
        
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self._optimize_context()
        
    def _optimize_context(self):
        if len(self.history) > MAX_HISTORY_LEN + 1:
            system_prompt_node = {"role": "system", "content": load_system_prompt()}
            recent_messages = self.history[-MAX_HISTORY_LEN:]
            self.history = [system_prompt_node] + recent_messages

    def get_context(self):
        return self.history

    def save_history_to_disk(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = os.path.join(log_dir, f"session_{timestamp}.json")
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
            print(f"\n[AI-Kane]: Сессия успешно сохранена: {filename}")
        except Exception as e:
            print(f"\n[Ошибка сохранения истории]: {e}")

    def load_history_from_disk(self, filename: str) -> bool:
        """
        Загружает историю диалога из указанного JSON-файла в папке logs.
        """
        # ИСПРАВЛЕНО: Убрали квадратные скобки, теперь это чистая строка
        log_dir = "logs"
        
        # ИСПРАВЛЕНО: Все отступы внутри метода строго выровнены
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        full_path = os.path.join(log_dir, filename)
        
        if not os.path.exists(full_path):
            print(f"\n[Ошибка]: Файл истории {full_path} не найден на диске.")
            return False
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                saved_history = json.load(f)
                
            if isinstance(saved_history, list) and len(saved_history) > 0:
                self.history = saved_history
                # Обновляем системный промпт на актуальный из файла system_prompt.md
                self.history[0] = {"role": "system", "content": load_system_prompt()}
                print(f"\n[AI-Kane]: Успешно восстановлен контекст из файла: {filename}")
                return True
            else:
                print(f"\n[Ошибка]: Неверная структура данных в файле {filename}.")
                return False
                
        except Exception as e:
            print(f"\n[Ошибка восстановления истории]: {e}")
            return False
