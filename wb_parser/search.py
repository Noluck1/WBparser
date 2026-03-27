import re

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus


class SearchMixin:

    def search(self, query, limit=30):
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(query)}"

        with self.driver_lock:
            if not self._ensure_driver_window():
                return []
            self.driver.get(url)
        self._human_behavior()

        products = self._collect_search_results(limit * 3)
        query_tokens = [token.lower() for token in re.findall(r"\w+", query) if len(token) >= 4]
        if query_tokens:
            filtered_products = []
            for product in products:
                haystack = str(product.get("name", "")).lower()
                if any(token in haystack for token in query_tokens):
                    filtered_products.append(product)
            if filtered_products:
                products = filtered_products

        products = products[:limit]
        detail_map = self._get_detail_products_map(
            [product["article"] for product in products],
            allow_browser_fallback=True,
        )
        results = [None] * len(products)

        max_workers = min(8, max(1, len(products)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._get_product_full_data,
                    int(product["article"]),
                    product.get("url"),
                    detail_map.get(str(product["article"])),
                ): index
                for index, product in enumerate(products[:limit])
            }

            for future in as_completed(futures):
                index = futures[future]
                product = dict(products[index])
                try:
                    full = future.result()
                except Exception as e:
                    print("Ошибка товара:", e)
                    full = {}
                product.update(full)
                results[index] = product

        finalized = []
        for product in [item for item in results if item]:
            finalized.append(
                self._finalize_product_data(
                    product,
                    detail_product=detail_map.get(str(product["article"])),
                )
            )

        return finalized
