# -*- coding: utf-8 -*-
import datetime

def get_system_time() -> str:
    """Возвращает текущую точную дату и время на сервере MarmAI."""
    now = datetime.datetime.now()
    return f"Текущее точное системное время: {now.strftime('%Y-%m-%d %H:%M:%S')}"
