# -*- coding: utf-8 -*-
from database.task_storage import create_task_db, get_all_tasks_db, update_task_status_db

def manage_tasks(action: str, title: str = "", description: str = "", priority: str = "medium", task_id: int = None, status: str = "") -> str:
    """
    Инструмент для управления таск-трекером спринтов проекта MarmAI.
    Поддерживает действия: 'create' (создать), 'list' (показать бэклог), 'update_status' (сменить статус).
    """
    VALID_STATUSES = {"backlog", "in_work", "in work", "testing", "done", "canceled"}

    if action == "create":
        if not title:
            return "❌ Ошибка: Для создания задачи обязательно укажите заголовок (title)."
        new_id = create_task_db(title, description, priority)
        return f"✅ Задача #{new_id} '{title}' успешно добавлена в бэклог [BACKLOG]!"
        
    elif action == "list":
        tasks = get_all_tasks_db()
        if not tasks:
            return "📋 Таск-трекер пуст. Активных задач в спринте нет."
        
        report = ["📋 **Текущее состояние спринта в tasktracker:**"]
        for t in tasks:
            # Красивые визуальные эмодзи-якоря под каждый из 5 статусов
            emoji_map = {
                "backlog": "⏳",
                "in_work": "⚡",
                "testing": "🧪",
                "done": "✅",
                "canceled": "❌"
            }
            status_display = t['status'].upper().replace("_", " ")
            emoji = emoji_map.get(t['status'], "🔹")
            
            report.append(f"- [{t['id']}] {emoji} *[{status_display}]* **{t['title']}** (Приоритет: {t['priority']})")
            if t['description']:
                report.append(f"  *{t['description']}*")
        return "\n".join(report)
        
    elif action == "update_status" or action == "close":
        if not task_id:
            return "❌ Ошибка: Укажите числовой идентификатор задачи (task_id)."
        
        # Если вызван старый экшен close — автоматически мапим на DONE
        target_status = status.lower().strip() if status else "done"
        if action == "close":
            target_status = "done"
            
        if target_status not in VALID_STATUSES:
            return f"❌ Ошибка: Неверный статус '{status}'. Доступны: BACKLOG, IN WORK, TESTING, DONE, CANCELED."
            
        success = update_task_status_db(task_id, target_status)
        status_upper = target_status.upper().replace("_", " ")
        return f"✅ Задача #{task_id} успешно переведена в статус [{status_upper}]!" if success else f"❌ Задача #{task_id} не найдена в SQLite."
        
    return "❌ Неизвестное действие. Используйте 'create', 'list' или 'update_status'."
