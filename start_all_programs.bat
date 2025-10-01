@echo off
chcp 65001 >nul
echo ========================================
echo    Запуск всех торговых программ
echo ========================================
echo.

echo Запуск программы просмотра тикеров...
start "Ticker Viewer" cmd /k "chcp 65001 >nul && python run_ticker_viewer.py"
timeout /t 3 /nobreak >nul

echo Запуск программы обучения моделей...
start "Trainer GUI" cmd /k "chcp 65001 >nul && python trainer_gui.py"
timeout /t 3 /nobreak >nul

echo Запуск основной торговой программы...
start "Trading Bot" cmd /k "chcp 65001 >nul && python trading_bot_main.py"

echo.
echo ========================================
echo Все программы запущены!
echo ========================================
echo.
echo Для остановки всех программ закройте это окно
echo или нажмите любую клавишу для выхода
pause >nul