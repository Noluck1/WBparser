import re


class UtilsMixin:

    def _build_supplier_link(self, supplier_id=None, supplier_link=None):
        if supplier_link:
            if supplier_link.startswith("http"):
                return supplier_link
            return f"https://www.wildberries.ru{supplier_link}"

        if supplier_id:
            return f"https://www.wildberries.ru/seller/{supplier_id}"

        return ""

    def _normalize_supplier_data(self, supplier_id=None, supplier_name="", supplier_link=None):
        supplier_id = str(supplier_id).strip() if supplier_id not in (None, "") else ""
        supplier_name = (supplier_name or "").strip()
        supplier_link = self._build_supplier_link(supplier_id=supplier_id, supplier_link=supplier_link)

        if not supplier_id and supplier_link and "/seller/" in supplier_link:
            supplier_id = supplier_link.rstrip("/").split("/seller/")[-1].split("?")[0].split("/")[0]

        if not supplier_id and not supplier_name and not supplier_link:
            return {}

        return {
            "supplier_id": supplier_id or None,
            "supplier_name": supplier_name or None,
            "supplier_link": supplier_link or None,
        }

    def _extract_supplier_from_card(self, data):
        if not isinstance(data, dict):
            return {}

        candidates = [
            data,
            data.get("selling") or {},
            data.get("seller") or {},
            data.get("supplier") or {},
        ]

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            supplier_id = (
                candidate.get("supplierId")
                or candidate.get("supplier_id")
                or candidate.get("supplierID")
                or candidate.get("id")
            )
            supplier_name = (
                candidate.get("trademark")
                or candidate.get("supplierName")
                or candidate.get("supplierFullName")
                or candidate.get("supplier")
                or candidate.get("name")
            )
            supplier_link = (
                candidate.get("supplierLink")
                or candidate.get("link")
                or candidate.get("url")
            )

            normalized = self._normalize_supplier_data(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                supplier_link=supplier_link,
            )
            if normalized.get("supplier_id") or normalized.get("supplier_name"):
                return normalized

        return {}

    def _first_non_empty(self, *values):
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            return value
        return None

    def _safe_int(self, value, default=0):
        try:
            if value in (None, ""):
                return default
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return default

    def _extract_country_from_characteristics(self, characteristics):
        if not isinstance(characteristics, list):
            return ""

        country_key_patterns = (
            "страна",
            "производ",
            "изготов",
            "made in",
            "country",
            "origin",
        )

        for item in characteristics:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name", "")).strip().lower()
            if not any(pattern in name for pattern in country_key_patterns):
                continue

            value = item.get("value")
            if value is None and item.get("values"):
                value = ", ".join(str(v) for v in item.get("values", []) if v)
            if value is None:
                continue

            normalized = self._normalize_country_name(value)
            if self._looks_like_country(normalized):
                return normalized

        return ""

    def _extract_country_from_text(self, text):
        text = str(text or "").strip()
        if not text:
            return ""

        patterns = [
            r"(?:страна\s+производства|страна\s+происхождения|страна-изготовитель|произведено\s+в|изготовлено\s+в)\s*[:\-]?\s*([А-Яа-яA-Za-z\-\s]{2,60})",
            r"(?:made\s+in|country\s+of\s+origin)\s*[:\-]?\s*([A-Za-z\-\s]{2,60})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            normalized = self._normalize_country_name(match.group(1))
            if self._looks_like_country(normalized):
                return normalized

        return ""

    def _extract_country_from_payload(self, payload):
        seen = set()
        return self._extract_country_from_payload_node(payload, seen)

    def _extract_country_from_payload_node(self, node, seen):
        if node is None:
            return ""

        node_id = id(node)
        if node_id in seen:
            return ""
        seen.add(node_id)

        if isinstance(node, dict):
            direct_keys = (
                "country",
                "countryName",
                "country_of_origin",
                "countryOfOrigin",
                "madeIn",
                "made_in",
                "manufacturerCountry",
                "producingCountry",
                "productionCountry",
            )
            for key in direct_keys:
                if key in node:
                    normalized = self._normalize_country_name(node.get(key))
                    if self._looks_like_country(normalized):
                        return normalized

            name = str(node.get("name", "")).strip().lower()
            if name:
                value = self._first_non_empty(node.get("value"), node.get("text"))
                if value is None and node.get("values"):
                    value = ", ".join(str(v) for v in node.get("values", []) if v)
                if value and any(token in name for token in ("страна", "производ", "изготов", "origin", "country")):
                    normalized = self._normalize_country_name(value)
                    if self._looks_like_country(normalized):
                        return normalized

            for key, value in node.items():
                key_text = str(key).lower()
                if any(token in key_text for token in ("country", "origin", "страна", "производ", "изготов")):
                    normalized = self._normalize_country_name(value)
                    if self._looks_like_country(normalized):
                        return normalized
                    nested_from_text = self._extract_country_from_text(value)
                    if nested_from_text:
                        return nested_from_text

            for value in node.values():
                nested = self._extract_country_from_payload_node(value, seen)
                if nested:
                    return nested

        elif isinstance(node, list):
            for item in node:
                nested = self._extract_country_from_payload_node(item, seen)
                if nested:
                    return nested

        elif isinstance(node, str):
            return self._extract_country_from_text(node)

        return ""

    def _normalize_country_name(self, value):
        text = str(value or "").strip()
        if not text:
            return ""

        text = re.sub(r"\s+", " ", text)
        text = text.strip(" .,:;|-")
        text = re.sub(r"^(страна\s+производства|страна\s+происхождения|страна-изготовитель|произведено\s+в|изготовлено\s+в)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
        text = text.strip(" .,:;|-")
        lowered = text.lower()

        aliases = {
            "рф": "Россия",
            "российская федерация": "Россия",
            "russia": "Россия",
            "ru": "Россия",
            "russian federation": "Россия",
            "china": "Китай",
            "turkey": "Турция",
            "belarus": "Беларусь",
            "italy": "Италия",
            "uzbekistan": "Узбекистан",
            "kazakhstan": "Казахстан",
        }
        if lowered in aliases:
            return aliases[lowered]

        return text

    def _looks_like_country(self, value):
        text = self._normalize_country_name(value)
        if not text:
            return False
        lowered = text.lower()
        blocked_tokens = (
            "размер",
            "длина",
            "ширина",
            "высота",
            "материал",
            "состав",
            "артикул",
            "бренд",
            "цвет",
            "модель",
            "пальто",
            "курт",
            "юбк",
            "плать",
            "жакет",
            "костюм",
            "см",
            "мм",
            "шт",
            "кг",
            "грам",
            "руб",
        )
        if any(token in lowered for token in blocked_tokens):
            return False
        if re.search(r"\d", lowered):
            return False
        if len(text) < 3 or len(text) > 40:
            return False
        if "," in text and "россия" not in lowered:
            return False
        words = [word for word in re.split(r"\s+", text) if word]
        return len(words) <= 4

    def _is_russia_country(self, value):
        normalized = self._normalize_country_name(value).lower()
        if not normalized:
            return False
        return bool(re.search(r"(^|[^a-zа-я])россия([^a-zа-я]|$)", normalized, flags=re.IGNORECASE))

    def _parse_price_value(self, price):
        text = str(price or "").strip()
        if not text:
            return None

        digits = re.findall(r"\d+", text)
        if not digits:
            return None

        try:
            return int("".join(digits))
        except ValueError:
            return None

    def _serialize_characteristics(self, characteristics):
        if not isinstance(characteristics, list):
            return ""

        parts = []
        for item in characteristics:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            value = str(item.get("value", "")).strip()
            if name or value:
                parts.append(f"{name}: {value}".strip(": "))

        return " | ".join(parts)

    def _extract_rating_from_card(self, data):
        rating = self._first_non_empty(
            data.get("reviewRating"),
            data.get("rating"),
            data.get("valuation"),
            data.get("imtRating"),
        )
        if rating is None:
            return None

        try:
            return float(rating)
        except (TypeError, ValueError):
            return None

    def _extract_feedbacks_from_card(self, data):
        feedbacks = self._first_non_empty(
            data.get("feedbacks"),
            data.get("feedbackCount"),
            data.get("commentsQty"),
            data.get("reviewCount"),
        )
        return self._safe_int(feedbacks, 0)

    def _extract_sizes_from_product(self, product):
        if not isinstance(product, dict):
            return ""

        sizes = product.get("sizes", [])
        if not isinstance(sizes, list):
            return ""

        raw_values = []
        for size_item in sizes:
            if not isinstance(size_item, dict):
                continue

            size_name = self._first_non_empty(
                size_item.get("origName"),
                size_item.get("name"),
                size_item.get("size"),
                size_item.get("techSize"),
                size_item.get("wbSize"),
            )
            if size_name:
                raw_values.append(size_name)

        return self._normalize_numeric_sizes(raw_values)

    def _normalize_numeric_sizes(self, values):
        if not isinstance(values, (list, tuple, set)):
            values = [values]

        result = []
        seen = set()

        blocked_tokens = (
            "остал",
            "налич",
            "отзыв",
            "рейтинг",
            "продав",
            "артикул",
            "см",
            "мм",
        )
        letter_size_pattern = re.compile(r"\b(?:xxxl|xxl|xl|xs|s|m|l|one\s*size|onesize|единый)\b", flags=re.IGNORECASE)
        numeric_size_pattern = re.compile(r"\b\d{2,3}(?:\s*[/-]\s*\d{2,3})?\b")

        for value in values:
            if value is None:
                continue

            text = str(value).strip()
            if not text:
                continue
            if len(text) > 24:
                continue

            lowered = text.lower()
            if any(token in lowered for token in blocked_tokens):
                continue

            raw_candidates = []
            raw_candidates.extend(letter_size_pattern.findall(text))
            raw_candidates.extend(numeric_size_pattern.findall(text))

            for candidate in raw_candidates:
                normalized_candidate = re.sub(r"\s+", "", str(candidate).upper())
                if not normalized_candidate or normalized_candidate in seen:
                    continue
                seen.add(normalized_candidate)
                result.append(normalized_candidate)

        return ", ".join(result)

    def _extract_product_from_payload(self, payload, article):
        if not isinstance(payload, dict):
            return {}

        products = payload.get("products")
        if not isinstance(products, list):
            products = payload.get("data", {}).get("products", [])
        if not isinstance(products, list):
            return {}

        article = self._safe_int(article, 0)
        for product in products:
            if not isinstance(product, dict):
                continue

            product_id = self._safe_int(
                self._first_non_empty(product.get("id"), product.get("nmId")),
                0,
            )
            if product_id == article:
                return product

        return {}

    def _parse_product_detail_data(self, product):
        if not isinstance(product, dict):
            return {}

        rating = self._first_non_empty(
            product.get("reviewRating"),
            product.get("nmReviewRating"),
            product.get("rating"),
            product.get("supplierRating"),
        )
        feedbacks = self._first_non_empty(
            product.get("nmFeedbacks"),
            product.get("feedbacks"),
            product.get("feedbackCount"),
            product.get("reviewCount"),
        )

        parsed = {}

        try:
            if rating is not None:
                parsed["rating"] = float(rating)
        except (TypeError, ValueError):
            pass

        if feedbacks is not None:
            parsed["feedbacks"] = self._safe_int(feedbacks, 0)

        return parsed

    def _extract_supplier_from_detail_product(self, product):
        if not isinstance(product, dict):
            return {}

        return self._normalize_supplier_data(
            supplier_id=product.get("supplierId"),
            supplier_name=product.get("supplier"),
        )
