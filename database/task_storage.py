# -*- coding: utf-8 -*-
import os
import sqlite3
import datetime
from typing import List, Dict, Any

DB_PATH = "tasks.db"

def init_task_db():
    """Инициализирует базу данных SQLite и автоматически обновляет структуру до 5 статусов."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ПРОВЕРКА МИГРАЦИИ: Проверяем, поддерживает ли база новые статусы
    try:
        cursor.execute("INSERT INTO tasks (title, status, priority, created_at, updated_at) VALUES ('test', 'in_work', 'low', '1', '1')")
        conn.rollback() # Если вставилось — всё отлично, миграция не нужна
    except sqlite3.IntegrityError:
        print("⚡ [SQLite] Обнаружена старая структура БД. Запуск автоматической миграции на 5 статусов...")
        
        # Переименовываем старую таблицу во временную
        cursor.execute("ALTER TABLE tasks RENAME TO _tasks_old")
        
        # Создаем новую таблицу с расширенным правилом CHECK
        cursor.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL CHECK(status IN ('backlog', 'in_work', 'testing', 'done', 'canceled')),
                priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
                git_commit_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Переносим старые данные, конвертируя 'in_progress' в 'in_work'
        cursor.execute("""
            INSERT INTO tasks (id, title, description, status, priority, git_commit_hash, created_at, updated_at)
            SELECT id, title, description, 
                   CASE WHEN status = 'in_progress' THEN 'in_work' ELSE status END,
                   priority, git_commit_hash, created_at, updated_at
            FROM _tasks_old
        """)
        
        # Удаляем временную старую таблицу
        cursor.execute("DROP TABLE _tasks_old")
        conn.commit()
        print("✅ [SQLite] Миграция успешно завершена! Данные сохранены и переведены на новые статусы.")

    # Создаем таблицу, если её вообще не было (первый запуск)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('backlog', 'in_work', 'testing', 'done', 'canceled')),
            priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
            git_commit_hash TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("📁 === [SQLite] База данных tasktracker (5 статусов) успешно подключена! ===")


def create_task_db(title: str, description: str = "", priority: str = "medium") -> int:
    """Создает новую задачу в бэклоге."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (title, description, status, priority, created_at, updated_at) VALUES (?, ?, 'backlog', ?, ?, ?)",
        (title, description, priority, now, now)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_all_tasks_db(status_filter: str = None) -> List[Dict[str, Any]]:
    """Возвращает список задач, отсортированных по приоритету и иерархии статусов."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status_filter:
        cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY id DESC", (status_filter.lower(),))
    else:
        # Умная сортировка: сначала задачи в работе, потом бэклог, тестирование, доделки и отмена
        cursor.execute("""
            SELECT * FROM tasks 
            ORDER BY 
              CASE status 
                WHEN 'in_work' THEN 1 
                WHEN 'testing' THEN 2 
                WHEN 'backlog' THEN 3 
                WHEN 'done' THEN 4 
                WHEN 'canceled' THEN 5 
              END, id DESC
        """)
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_task_status_db(task_id: int, status: str, commit_hash: str = None) -> bool:
    """Обновляет статус задачи на любой из 5 доступных."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    clean_status = status.lower().strip()
    if clean_status == "in work":
        clean_status = "in_work"
        
    if commit_hash:
        cursor.execute(
            "UPDATE tasks SET status = ?, git_commit_hash = ?, updated_at = ? WHERE id = ?",
            (clean_status, commit_hash, now, task_id)
        )
    else:
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (clean_status, now, task_id)
        )
        
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
