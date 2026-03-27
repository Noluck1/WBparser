import requests


class ProductMixin:

    def _build_image_url(self, host_number, vol, part, article, image_size, image_index):
        return (
            f"https://basket-{host_number:02d}.wbbasket.ru/"
            f"vol{vol}/part{part}/{article}/images/{image_size}/{image_index}.webp"
        )

    def _resolve_image_base(self, article):
        article = self._safe_int(article, 0)
        if article <= 0:
            return None

        vol = article // 100000
        part = article // 1000
        cache_key = f"image_base:{vol}:{part}"
        cached = self.page_data_cache.get(cache_key)
        if cached:
            return cached

        preferred_host = max(1, min(30, vol // 144 + 1))
        host_candidates = [preferred_host]
        for offset in range(1, 31):
            lower = preferred_host - offset
            upper = preferred_host + offset
            if lower >= 1:
                host_candidates.append(lower)
            if upper <= 30:
                host_candidates.append(upper)
        host_candidates.extend([host for host in range(1, 31) if host not in host_candidates])

        size_candidates = ["c246x328", "big"]

        for host_number in host_candidates:
            for image_size in size_candidates:
                url = self._build_image_url(host_number, vol, part, article, image_size, 1)
                try:
                    response = self.session.get(url, timeout=5)
                    content_type = response.headers.get("Content-Type", "").lower()
                    if response.status_code == 200 and "image" in content_type:
                        base = {
                            "host_number": host_number,
                            "image_size": image_size,
                            "vol": vol,
                            "part": part,
                        }
                        self.page_data_cache[cache_key] = base
                        return base
                except requests.exceptions.RequestException:
                    continue

        fallback = {
            "host_number": preferred_host,
            "image_size": "c246x328",
            "vol": vol,
            "part": part,
        }
        self.page_data_cache[cache_key] = fallback
        return fallback

    def _build_product_images(self, article, max_images=14):
        base = self._resolve_image_base(article)
        if not base:
            return []

        images = []
        miss_count = 0
        for image_index in range(1, max_images + 1):
            url = self._build_image_url(
                base["host_number"],
                base["vol"],
                base["part"],
                article,
                base["image_size"],
                image_index,
            )

            if image_index <= 3:
                try:
                    response = self.session.get(url, timeout=5)
                    content_type = response.headers.get("Content-Type", "").lower()
                    if response.status_code != 200 or "image" not in content_type:
                        miss_count += 1
                        if miss_count >= 2 and images:
                            break
                        continue
                except requests.exceptions.RequestException:
                    miss_count += 1
                    if miss_count >= 2 and images:
                        break
                    continue

            images.append(url)

        return images

    def _get_product_full_data(self, article, product_url=None, detail_product=None, allow_browser_fallback=False):
        try:
            article = int(article)

            vol = article // 100000
            part = article // 1000

            cdn_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

            description = ""
            characteristics = []
            card_data = {}
            supplier_data = self._extract_supplier_from_detail_product(detail_product)
            sizes = ""
            rating = None
            feedbacks = 0
            stocks = None

            for cdn in cdn_list:
                url = (
                    f"https://rst-basket-cdn-{cdn:02d}.geobasket.ru/"
                    f"vol{vol}/part{part}/{article}/info/ru/card.json"
                )

                try:
                    response = self.session.get(url, timeout=5)

                    if response.status_code != 200:
                        continue

                    card_data = response.json()
                    description = card_data.get("description", "")
                    rating = self._extract_rating_from_card(card_data)
                    feedbacks = self._extract_feedbacks_from_card(card_data)

                    for opt in card_data.get("options", []):
                        characteristics.append({
                            "name": opt.get("name"),
                            "value": opt.get("value"),
                            "is_variable": opt.get("is_variable", False),
                            "values": opt.get("variable_values", []),
                        })

                    if not supplier_data:
                        supplier_data = self._extract_supplier_from_card(card_data)
                    break

                except requests.exceptions.RequestException:
                    continue

            images = self._build_product_images(article)

            supplier_id = supplier_data.get("supplier_id")

            if supplier_id and supplier_id in self.suppliers_cache:
                supplier_data = {
                    **self.suppliers_cache[supplier_id],
                    **{k: v for k, v in supplier_data.items() if v},
                }

            if supplier_id and (
                not supplier_data.get("supplier_name")
                or len(supplier_data["supplier_name"].strip()) < 2
            ):
                supplier_data = self._get_supplier_info(supplier_id) or supplier_data

            if supplier_id and not supplier_data.get("supplier_name"):
                supplier_data = self._get_supplier_from_catalog(supplier_id) or supplier_data

            supplier_data = self._normalize_supplier_data(
                supplier_id=supplier_data.get("supplier_id"),
                supplier_name=supplier_data.get("supplier_name"),
                supplier_link=supplier_data.get("supplier_link"),
            )

            if supplier_data.get("supplier_id"):
                self.suppliers_cache[supplier_data["supplier_id"]] = supplier_data

            detail_data = self._get_product_detail_data(
                article,
                product_url=product_url,
                detail_product=detail_product,
                allow_browser_fallback=allow_browser_fallback,
            )
            if detail_data.get("rating") is not None:
                rating = detail_data["rating"]
            if detail_data.get("feedbacks") is not None:
                feedbacks = detail_data["feedbacks"]

            sizes_data = self._get_product_sizes_data(
                article,
                allow_browser_fallback=allow_browser_fallback,
            )
            if sizes_data.get("sizes"):
                sizes = self._normalize_numeric_sizes(sizes_data["sizes"].split(","))

            if not sizes and product_url:
                page_sizes_data = self._get_sizes_from_product_page(product_url)
                if page_sizes_data.get("sizes"):
                    sizes = self._normalize_numeric_sizes(page_sizes_data["sizes"].split(","))

            stocks_data = {"stocks": len(sizes.split(", ")) if sizes else None}
            if stocks_data.get("stocks") is None:
                stocks_data = self._get_product_stocks_data(article)
            if stocks_data.get("stocks") is not None:
                stocks = stocks_data["stocks"]

            country_of_origin = (
                self._extract_country_from_characteristics(characteristics)
                or self._extract_country_from_payload(card_data)
                or self._extract_country_from_payload(detail_product)
                or self._extract_country_from_text(description)
            )

            return {
                "images": ",".join(images),
                "description": description,
                "characteristics": characteristics,
                "country_of_origin": country_of_origin,
                "sizes": sizes,
                "stocks": stocks,
                "rating": rating,
                "feedbacks": feedbacks,
                **supplier_data,
            }

        except Exception as e:
            print("Ошибка:", e)
            return {}

    def _finalize_product_data(self, product, detail_product=None):
        article = self._safe_int(product.get("article"), 0)
        product_url = product.get("url")

        if article <= 0:
            return product

        if product.get("rating") is None or not product.get("feedbacks"):
            detail_data = self._get_product_detail_data(
                article,
                product_url=product_url,
                detail_product=detail_product,
                allow_browser_fallback=True,
            )
            if detail_data.get("rating") is not None:
                product["rating"] = detail_data["rating"]
            if detail_data.get("feedbacks") is not None:
                product["feedbacks"] = detail_data["feedbacks"]

        if not product.get("sizes"):
            sizes_data = self._get_product_sizes_data(
                article,
                allow_browser_fallback=True,
            )
            if sizes_data.get("sizes"):
                product["sizes"] = self._normalize_numeric_sizes(
                    sizes_data["sizes"].split(",")
                )

        if not product.get("sizes") and product_url:
            page_sizes_data = self._get_sizes_from_product_page(product_url)
            if page_sizes_data.get("sizes"):
                product["sizes"] = self._normalize_numeric_sizes(
                    page_sizes_data["sizes"].split(",")
                )

        if product.get("stocks") is None:
            stocks_data = self._get_public_stocks_data(product_url)
            if stocks_data.get("stocks") is not None:
                product["stocks"] = stocks_data["stocks"]
            elif product.get("sizes"):
                product["stocks"] = len(product["sizes"].split(", "))

        if not product.get("supplier_link") or not product.get("supplier_name"):
            supplier_data = self._get_supplier_from_product_page(product_url)
            if supplier_data:
                product.update({k: v for k, v in supplier_data.items() if v})

        if not product.get("country_of_origin"):
            product["country_of_origin"] = (
                self._extract_country_from_characteristics(product.get("characteristics", []))
                or self._extract_country_from_payload(detail_product)
                or self._extract_country_from_text(product.get("description", ""))
            )

        if not product.get("images"):
            product["images"] = ",".join(self._build_product_images(article))

        return product
