from wb_parser import WBParser


# -----------------------------
# запуск
# -----------------------------
if __name__ == "__main__":
    parser = WBParser()

    try:
        parser.warmup()

        data = parser.search("пальто из натуральной шерсти", limit=30)
        excel_info = parser.save_to_excel(
            data,
            all_filename="wb_catalog.xlsx",
            filtered_filename="wb_filtered.xlsx",
        )

        for item in data:
            print("\n---")
            print("Название:", item["name"])
            print("Цена:", item["price"])
            print("Ссылка:", item["url"])
            print("Артикул:", item["article"])

            print("Продавец:", item.get("supplier_name"))
            print("Ссылка на продавца:", item.get("supplier_link"))
            print("Размеры:", item.get("sizes"))
            print("Остатки:", item.get("stocks"))
            print("Рейтинг:", item.get("rating"))
            print("Количество отзывов:", item.get("feedbacks"))

            print("Описание:", item["description"])
            print("Характеристики:", item["characteristics"])
            print("Картинки:", item.get("images"))

        print("\nСохранено в XLSX:")
        print("Полный каталог:", excel_info["all_path"], "| строк:", excel_info["all_count"])
        print("Фильтр:", excel_info["filtered_path"], "| строк:", excel_info["filtered_count"])

    finally:
        parser.close()
