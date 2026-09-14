# -*- coding: utf-8 -*-
import os
import sqlite3
import datetime
from typing import List, Dict, Any

DB_PATH = "tasks.db"

def init_task_db():
    """Инициализирует локальную базу данных SQLite и создает таблицу задач."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Создаем таблицу задач спринта
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('backlog', 'in_progress', 'done')),
            priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
            git_commit_hash TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("📁 === [SQLite] База данных tasktracker успешно инициализирована! ===")

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
    """Возвращает список задач."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Чтобы возвращать данные в виде словарей
    cursor = conn.cursor()
    
    if status_filter:
        cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY id DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM tasks ORDER BY status DESC, id DESC")
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_task_status_db(task_id: int, status: str, commit_hash: str = None) -> bool:
    """Обновляет статус задачи (например, переводит в done)."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if commit_hash:
        cursor.execute(
            "UPDATE tasks SET status = ?, git_commit_hash = ?, updated_at = ? WHERE id = ?",
            (status, commit_hash, now, task_id)
        )
    else:
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id)
        )
        
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
