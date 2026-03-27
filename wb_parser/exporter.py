import os

import pandas as pd


class ExportMixin:

    def save_to_excel(self, data, all_filename="wb_catalog.xlsx", filtered_filename="wb_filtered.xlsx"):
        columns = [
            "name",
            "price",
            "url",
            "article",
            "supplier_name",
            "supplier_link",
            "country_of_origin",
            "sizes",
            "stocks",
            "rating",
            "feedbacks",
            "description",
            "characteristics",
            "images",
        ]
        rows = []
        price_values = []

        for item in data:
            characteristics = item.get("characteristics", [])
            country_of_origin = (
                item.get("country_of_origin")
                or self._extract_country_from_characteristics(characteristics)
                or self._extract_country_from_text(item.get("description", ""))
            )
            country_of_origin = self._normalize_country_name(country_of_origin)

            price_value = self._parse_price_value(item.get("price"))
            price_values.append(price_value)

            rows.append({
                "name": item.get("name"),
                "price": item.get("price"),
                "url": item.get("url"),
                "article": item.get("article"),
                "supplier_name": item.get("supplier_name"),
                "supplier_link": item.get("supplier_link"),
                "country_of_origin": country_of_origin,
                "sizes": item.get("sizes"),
                "stocks": item.get("stocks"),
                "rating": item.get("rating"),
                "feedbacks": item.get("feedbacks"),
                "description": item.get("description"),
                "characteristics": self._serialize_characteristics(characteristics),
                "images": item.get("images"),
            })

        df = pd.DataFrame(rows, columns=columns)
        all_path = os.path.abspath(all_filename)
        filtered_path = os.path.abspath(filtered_filename)

        df.to_excel(all_path, index=False)
        price_series = pd.to_numeric(pd.Series(price_values), errors="coerce")
        is_russia = df["country_of_origin"].fillna("").apply(self._is_russia_country)

        filtered_df = df[
            (pd.to_numeric(df["rating"], errors="coerce") >= 4.5)
            & (price_series <= 10000)
            & is_russia
        ].copy()
        filtered_df.to_excel(filtered_path, index=False)

        return {
            "all_path": all_path,
            "filtered_path": filtered_path,
            "all_count": len(df),
            "filtered_count": len(filtered_df),
        }
