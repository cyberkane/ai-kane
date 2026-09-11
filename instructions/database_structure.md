# Архитектура Базы Данных MarmAI (InfluxDB 3.0)
**Bucket (База данных):** `marmai_observability`

---

## 1. Таблица: `agent_configuration`
Хранит слоистую личность агента, правила безопасности и архитектурные гайдлайны.

### TAGS (Индексируемые поля)
* `project_id` (String) — ID проекта (`global`, `marmai-backend`)
* `config_type` (String) — Тип (`persona`, `architecture`, `security`)
* `priority_level` (String) — Приоритет (`1_base`, `2_knowledge`, `3_context`, `4_mood`)
* `sub_category` (String) — Подкатегория (`identity`, `tech_stack`, `emotional_state`)
* `version` (String) — Версия конфига (`latest`, `v1.0.0`)

### FIELDS (Данные)
* `title` (String) — Название правила / среза
* `content_text` (String) — Полный текст инструкции или системного промпта
* `author` (String) — Кто внес изменения

---

## 2. Таблица: `file_activity`
Логирует фокус и действия разработчика в IDE в реальном времени.

### TAGS (Индексируемые поля)
* `project_id` (String) — Название открытого проекта
* `file_path` (String) — Путь к файлу (`src/auth/jwt.py`)
* `event_type` (String) — Действие (`open`, `save`, `edit`, `focus`)
* `language` (String) — Язык кода (`python`, `typescript`)

### FIELDS (Данные)
* `cursor_line` (Integer) — Номер строки курсора
* `cursor_column` (Integer) — Номер символа в строке
* `lines_changed` (Integer) — Сколько строк изменилось при сохранении
* `file_size_bytes` (Integer) — Вес файла в байтах

---

## 3. Таблица: `agent_telemetry`
Трейсинг и аудит каждого шага графа LangGraph (Llama 3.1).

### TAGS (Индексируемые поля)
* `session_id` (String) — ID диалога с пользователем
* `graph_name` (String) — Имя графа (`code_refactor_flow`)
* `node_name` (String) — Узел графа (`retrieve_node`)
* `model_name` (String) — Какая модель отвечала (`llama3.1:8b`)
* `status` (String) — Статус (`success`, `error`)

### FIELDS (Данные)
* `prompt_tokens` (Integer) — Токены на входе
* `completion_tokens` (Integer) — Токены на выходе
* `latency_ms` (Integer) — Время выполнения шага
* `tool_called` (String) — Какой инструмент вызывался
* `input_payload` (String/JSON) — Входящий JSON
* `output_payload` (String/JSON) — Ответ модели в JSON
* `error_message` (String) — Текст ошибки

---

## 4. Таблица: `vcs_history`
Хронология Git-коммитов для контекста изменений кодовой базы.

### TAGS (Индексируемые поля)
* `project_id` (String) — Имя репозитория
* `commit_hash` (String) — Хэш коммита (`a8f3c21`)
* `author` (String) — Автор коммита
* `branch` (String) — Ветка (`main`)

### FIELDS (Данные)
* `commit_message` (String) — Текст коммита
* `files_added` (String) — Список добавленных файлов через запятую
* `files_modified` (String) — Список измененных файлов
* `insertions` (Integer) — Добавлено строк кода
* `deletions` (Integer) — Удалено строк кода

---

## 5. Таблица: `agent_logs`
Логи работы агента
### TAGS (Индексируемые поля)
* `project_id` (String) — Имя репозитория
* `commit_hash` (String) — Хэш лога (`a8f3c21`)
* `subsystem` (String) — Подсистема
* `branch` (String) — Ветка (`main`)

### FIELDS (Данные)
* `log_message` (String) — Текст коммита
* `log_level` (String) — Список добавленных файлов через запятую
* `message_id` (String) — Список измененных файлов
* `time` (Time) — Время записи