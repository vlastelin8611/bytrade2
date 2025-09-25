from src.tools.ticker_data_loader import TickerDataLoader

def main():
    # Создаем экземпляр загрузчика данных
    loader = TickerDataLoader()
    
    # Сначала загружаем все данные тикеров
    loader.load_tickers_data()
    
    # Получаем исторические данные для BTCUSDT
    data = loader.get_historical_data('BTCUSDT')
    
    if data:
        # Выводим информацию о загруженных данных
        print(f'Загружено {len(data)} записей')
        print('Первые 3 записи:')
        for d in data[:3]:
            print(f"Время: {d.get('timestamp')}, Цена: {d.get('close')}")
    else:
        print("Данные для BTCUSDT не найдены. Убедитесь, что программа просмотра тикеров запущена и собрала данные.")

if __name__ == "__main__":
    main()