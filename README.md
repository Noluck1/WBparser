1. Сам парсер лежит в пакете `wb_parser/core.py`: там объявлен класс `WBParser`, который собирается из миксинов.

2. Точка запуска находится в `parser.py`.

3. Логика парсера разнесена по файлам:
   - `wb_parser/base.py` — Selenium/драйвер, вкладки, базовые операции  
   - `wb_parser/api.py` — API-запросы WB  
   - `wb_parser/product.py` — сбор полной карточки товара (фото/страны/размеры)  
   - `wb_parser/search.py` — поиск и orchestration  
   - `wb_parser/exporter.py` — выгрузка в Excel  
   - `wb_parser/utils.py` — вспомогательные функции  
