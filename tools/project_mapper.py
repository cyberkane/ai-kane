# -*- coding: utf-8 -*-
import os
import re

def generate_project_architecture(root_dir: str = ".") -> str:
    """
    Сканирует директорию проекта, строит дерево файлов, анализирует зависимости
    и сохраняет полную архитектурную карту в файл project_architecture.md.
    """
    output_path = "project_architecture.md"
    ignore_dirs = {".venv", ".git", ".pytest_cache", "__pycache__", "node_modules"}
    
    markdown_lines = [
        "# 🗺️ Архитектурная карта проекта MarmAI Gateway\n",
        f"**Последнее обновление:** {os.popen('echo %date% %time%').read().strip()}\n",
        "## 📂 Структура каталогов и файлов\n",
        "```text"
    ]
    
    # 1. Строим дерево файлов
    for root, dirs, files in os.walk(root_dir):
        # Фильтруем игнорируемые папки на лету
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        sub_dir = os.path.basename(root)
        
        if sub_dir and sub_dir != ".":
            markdown_lines.append(f"{indent}├── {sub_dir}/")
            
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            if f.endswith((".py", ".md", ".ini", ".env")):
                markdown_lines.append(f"{sub_indent}├── {f}")
                
    markdown_lines.append("```\n")
    markdown_lines.append("## 🔬 Анализ ключевых модулей и зависимостей\n")
    
    # 2. Анализируем импорты в ключевых файлах
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith(".py") and f != "project_mapper.py":
                file_path = os.path.join(root, f)
                rel_path = os.path.relpath(file_path, root_dir)
                
                try:
                    with open(file_path, "r", encoding="utf-8") as file_content:
                        content = file_content.read()
                        
                    # Ищем локальные импорты (from database... или import tools...)
                    imports = re.findall(r'^(?:from|import)\s+([\w\.]+)', content, re.MULTILINE)
                    local_imports = [imp for imp in imports if any(p in imp for p in ["database", "functions", "tools", "metrics"])]
                    
                    if local_imports:
                        markdown_lines.append(f"### 📄 `{rel_path}`")
                        markdown_lines.append("**Связанные компоненты:**")
                        for imp in set(local_imports):
                            markdown_lines.append(f"- 🔗 `{imp}`")
                        markdown_lines.append("")
                except Exception:
                    pass

    final_markdown = "\n".join(markdown_lines)
    
    # Записываем отчет на диск
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_markdown)
        
    return f"✅ Архитектурная карта успешно сохранена в '{output_path}' и готова к отправке в Dragonfly RAM!"