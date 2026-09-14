# -*- coding: utf-8 -*-
from database.task_storage import create_task_db, get_all_tasks_db, update_task_status_db

def manage_tasks(action: str, title: str = "", description: str = "", priority: str = "medium", task_id: int = None, status: str = "") -> str:
    """
    Инструмент для управления таск-трекером (бэклогом и спринтами проекта MarmAI).
    Поддерживает действия: 'create' (создать), 'list' (показать всё), 'close' (закрыть задачу).
    """
    if action == "create":
        if not title:
            return "❌ Ошибка: Для создания задачи обязательно укажите заголовок (title)."
        new_id = create_task_db(title, description, priority)
        return f"✅ Задача #{new_id} '{title}' успешно добавлена в бэклог!"
        
    elif action == "list":
        tasks = get_all_tasks_db()
        if not tasks:
            return "📋 Таск-трекер пуст. Активных задач нет."
        
        report = ["📋 **Текущие задачи в tasktracker:**"]
        for t in tasks:
            status_emoji = "⏳" if t['status'] == "backlog" else "⚡" if t['status'] == "in_progress" else "✅"
            report.append(f"- [{t['id']}] {status_emoji} *[{t['status'].upper()}]* **{t['title']}** (Приоритет: {t['priority']})")
            if t['description']:
                report.append(f"  *{t['description']}*")
        return "\n".join(report)
        
    elif action == "close":
        if not task_id:
            return "❌ Ошибка: Для закрытия задачи укажите её ID (task_id)."
        success = update_task_status_db(task_id, "done")
        return f"✅ Задача #{task_id} успешно переведена в статус DONE!" if success else f"❌ Задача #{task_id} не найдена."
        
    return "❌ Неизвестное действие. Используйте 'create', 'list' или 'close'."
