@echo off
chcp 65001 >nul
cls
echo ========================================
echo    Запуск всех торговых программ
echo ========================================
echo.

echo [1/3] Запуск программы просмотра тикеров...
start "Ticker Viewer" cmd /k "chcp 65001 >nul && python run_ticker_viewer.py"
timeout /t 3 /nobreak >nul

echo [2/3] Запуск программы обучения моделей...
start "Trainer GUI" cmd /k "chcp 65001 >nul && python trainer_gui.py"
timeout /t 3 /nobreak >nul

echo [3/3] Запуск основной торговой программы...
start "Trading Bot" cmd /k "chcp 65001 >nul && python trading_bot_main.py"
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo Все программы запущены успешно!
echo ========================================
echo.
echo Открыто 3 окна:
echo - Ticker Viewer (просмотр тикеров)
echo - Trainer GUI (обучение моделей)
echo - Trading Bot (торговая программа)
echo.
echo Нажмите любую клавишу для выхода...
pause >nul