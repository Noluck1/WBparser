1. Сам парсер лежит в пакете wb_parser/core.py: там объявлен класс WBParser, который собирается из миксинов.
2. Точка запуска находится в parser.py
3. Логика парсера разнесена по файлам:
  3.1 wb_parser/base.py — Selenium/драйвер, вкладки, базовые операции
  3.2 wb_parser/api.py — API-запросы WB
  3.3 wb_parser/product.py — сбор полной карточки товара (включая фото/страны/размеры)
  3.4 wb_parser/search.py — поиск и orchestration
  3.5 wb_parser/exporter.py — выгрузка в Excel
  3.6 wb_parser/utils.py — вспомогательные функции
