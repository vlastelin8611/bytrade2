#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для перехвата и записи логов в текстовый файл
"""

import sys
import os
import logging
import datetime
from pathlib import Path
import io

class TerminalLogHandler(logging.Handler):
    """
    Обработчик логов, который перехватывает все сообщения и записывает их в текстовый файл.
    Также перенаправляет вывод в стандартный поток вывода.
    """
    
    def __init__(self, log_dir='logs', filename_prefix='terminal_log', level=logging.DEBUG):
        """
        Инициализация обработчика логов
        
        Args:
            log_dir (str): Директория для сохранения логов
            filename_prefix (str): Префикс для имени файла логов
            level (int): Уровень логирования
        """
        super().__init__(level)
        
        # Создаем директорию для логов, если она не существует
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # Формируем имя файла с текущей датой и временем
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = self.log_dir / f"{filename_prefix}_{current_time}.txt"
        
        # Открываем файл для записи
        self.log_file = open(self.log_file_path, 'w', encoding='utf-8')
        
        # Устанавливаем форматтер для логов
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Сохраняем оригинальные stdout и stderr
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        
        # Перехватываем стандартные потоки вывода
        sys.stdout = self
        sys.stderr = self
        
        # Инициализируем буфер для вывода
        self.buffer = io.StringIO()
        
        # Логируем начало записи
        self.log_file.write(f"=== Начало записи логов {current_time} ===\n")
        self.log_file.flush()
        
    def emit(self, record):
        """
        Записывает сообщение лога в файл
        
        Args:
            record: Запись лога
        """
        try:
            msg = self.format(record)
            self.log_file.write(f"{msg}\n")
            self.log_file.flush()
        except Exception:
            self.handleError(record)
    
    def write(self, message):
        """
        Перехватывает вывод из stdout/stderr и записывает в файл
        
        Args:
            message (str): Сообщение для записи
        """
        if message and not message.isspace():
            # Записываем в файл
            self.log_file.write(message)
            self.log_file.flush()
            
            # Также выводим в оригинальный stdout
            self.stdout.write(message)
            
            # Добавляем в буфер для возможного последующего использования
            self.buffer.write(message)
    
    def flush(self):
        """
        Сбрасывает буфер вывода
        """
        self.log_file.flush()
        self.stdout.flush()
        self.buffer.flush()
    
    def close(self):
        """
        Закрывает файл логов и восстанавливает стандартные потоки вывода
        """
        # Восстанавливаем оригинальные stdout и stderr
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        
        # Закрываем файл
        if self.log_file:
            self.log_file.write(f"\n=== Конец записи логов {datetime.datetime.now().strftime('%Y%m%d_%H%M%S')} ===\n")
            self.log_file.close()
            self.log_file = None
        
        # Закрываем буфер
        self.buffer.close()
        
        super().close()

def setup_terminal_logging(log_dir='logs', filename_prefix='terminal_log', level=logging.DEBUG):
    """
    Настраивает перехват и запись логов терминала
    
    Args:
        log_dir (str): Директория для сохранения логов
        filename_prefix (str): Префикс для имени файла логов
        level (int): Уровень логирования
        
    Returns:
        TerminalLogHandler: Созданный обработчик логов
    """
    # Создаем и настраиваем обработчик логов
    handler = TerminalLogHandler(log_dir, filename_prefix, level)
    
    # Добавляем обработчик к корневому логгеру
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    
    # Устанавливаем уровень логирования
    if root_logger.level > level or root_logger.level == 0:
        root_logger.setLevel(level)
    
    return handler