#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска отдельного приложения просмотра тикеров Bybit
"""

import sys
import tkinter as tk
from pathlib import Path

# Импортируем TickerViewerApp из модуля ticker_viewer_gui
from src.tools.ticker_viewer_gui import TickerViewerApp

def main():
    """Основная функция для запуска приложения тикеров"""
    root = tk.Tk()
    app = TickerViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()