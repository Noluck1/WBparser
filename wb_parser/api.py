import json

import requests
from selenium.webdriver.common.by import By
from urllib.parse import quote_plus

class ApiMixin:

    def _fetch_json_in_browser(self, url):
        try:
            return self.driver.execute_async_script(
                """
                const url = arguments[0];
                const done = arguments[arguments.length - 1];

                fetch(url, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json, text/plain, */*'
                    }
                })
                .then(async (response) => {
                    const text = await response.text();
                    done({
                        ok: response.ok,
                        status: response.status,
                        text: text
                    });
                })
                .catch((error) => {
                    done({
                        ok: false,
                        status: 0,
                        error: String(error)
                    });
                });
                """,
                url,
            )
        except Exception:
            return {}

    def _fetch_json_via_browser_tab(self, url):
        original_window = self._open_in_new_tab(url)
        if not original_window:
            return {}

        try:
            raw_text = self.driver.execute_script(
                "return document.body ? document.body.innerText : '';"
            )
            return {
                "ok": bool(raw_text),
                "status": 200 if raw_text else 0,
                "text": raw_text or "",
            }

        except Exception:
            return {}

        finally:
            self._close_current_tab(original_window)

    def _request_json(self, url, headers=None, allow_browser_fallback=True):
        try:
            resp = self.session.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

        if not allow_browser_fallback:
            return {}

        for response in (
            self._fetch_json_in_browser(url),
            self._fetch_json_via_browser_tab(url),
        ):
            if response and response.get("ok") and response.get("text"):
                try:
                    return json.loads(response["text"])
                except Exception:
                    pass

        return {}

    def _get_detail_products_map(self, articles, allow_browser_fallback=True):
        articles = [str(self._safe_int(article, 0)) for article in articles if self._safe_int(article, 0) > 0]
        if not articles:
            return {}

        detail_map = {}
        chunk_size = 30

        for start in range(0, len(articles), chunk_size):
            chunk = articles[start:start + chunk_size]
            url = (
                "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
                "?appType=1&curr=rub&dest=-1257786&spp=30"
                "&hide_vflags=4294967296&ab_testid=pmb_03&lang=ru"
                f"&nm={';'.join(chunk)}"
            )
            data = self._request_json(
                url,
                headers={"Referer": "https://www.wildberries.ru/"},
                allow_browser_fallback=allow_browser_fallback,
            )
            products = data.get("products", [])
            if not isinstance(products, list):
                continue

            for product in products:
                if not isinstance(product, dict):
                    continue
                article = str(self._safe_int(self._first_non_empty(product.get("id"), product.get("nmId")), 0))
                if article != "0":
                    detail_map[article] = product

        return detail_map

    def _get_sizes_from_product_page(self, product_url):
        if not product_url:
            return {}

        original_window = self._open_in_new_tab(product_url)
        if not original_window:
            return {}

        try:
            raw_sizes = self.driver.execute_script(
                """
                const selectors = [
                    '.sizes-list__item',
                    '.sizes-list__button',
                    '.sizes-list__size',
                    '.size-list__item',
                    '.j-size',
                    '[class*="sizes-list"] button',
                    '[class*="size"] button',
                    '[class*="size"] li',
                    '[class*="option"] button',
                    '[data-link*="size"]',
                    '[data-size]'
                ];

                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                };

                const isAvailable = (el) => {
                    const cls = (el.className || '').toString().toLowerCase();
                    const ariaDisabled = (el.getAttribute('aria-disabled') || '').toLowerCase();
                    return !el.disabled
                        && ariaDisabled !== 'true'
                        && !cls.includes('disabled')
                        && !cls.includes('sold-out')
                        && !cls.includes('unavailable')
                        && !cls.includes('out-of-stock');
                };

                const values = [];
                const seen = new Set();

                for (const selector of selectors) {
                    for (const el of document.querySelectorAll(selector)) {
                        if (!isVisible(el) || !isAvailable(el)) {
                            continue;
                        }

                        const text = (el.innerText || el.textContent || '').trim();
                        if (!text || seen.has(text)) {
                            continue;
                        }

                        seen.add(text);
                        values.push(text);
                    }
                }

                return values;
                """
            )

            sizes = self._normalize_numeric_sizes(raw_sizes or [])
            if not sizes:
                return {}

            return {"sizes": sizes}

        except Exception:
            return {}

        finally:
            self._close_current_tab(original_window)

    def _get_public_stocks_data(self, product_url):
        if not product_url:
            return {}

        original_window = self._open_in_new_tab(product_url)
        if not original_window:
            return {}

        try:
            stock_data = self.driver.execute_script(
                """
                const bodyText = (document.body ? document.body.innerText : '') || '';
                const patterns = [
                    /Осталось\\s+([0-9]{1,4})/i,
                    /Осталось\\s+всего\\s+([0-9]{1,4})/i,
                    /([0-9]{1,4})\\s*шт\\.?\\s*осталось/i,
                    /В наличии\\s+([0-9]{1,4})/i
                ];

                for (const pattern of patterns) {
                    const match = bodyText.match(pattern);
                    if (match) {
                        return {
                            exact: parseInt(match[1], 10),
                            sizesCount: 0
                        };
                    }
                }

                const selectors = [
                    '.sizes-list__item',
                    '.sizes-list__button',
                    '.sizes-list__size',
                    '.size-list__item',
                    '.j-size',
                    '[class*="sizes-list"] button',
                    '[class*="size"] button',
                    '[class*="size"] li',
                    '[class*="option"] button',
                    '[data-link*="size"]',
                    '[data-size]'
                ];

                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                };

                const isAvailable = (el) => {
                    const cls = (el.className || '').toString().toLowerCase();
                    const ariaDisabled = (el.getAttribute('aria-disabled') || '').toLowerCase();
                    return !el.disabled
                        && ariaDisabled !== 'true'
                        && !cls.includes('disabled')
                        && !cls.includes('sold-out')
                        && !cls.includes('unavailable')
                        && !cls.includes('out-of-stock');
                };

                const seen = new Set();
                let count = 0;

                for (const selector of selectors) {
                    for (const el of document.querySelectorAll(selector)) {
                        if (!isVisible(el) || !isAvailable(el)) {
                            continue;
                        }

                        const text = (el.innerText || el.textContent || '').trim();
                        const match = text.match(/\\b\\d{2,3}\\b/);
                        if (!match) {
                            continue;
                        }

                        const size = match[0];
                        if (seen.has(size)) {
                            continue;
                        }

                        seen.add(size);
                        count += 1;
                    }
                }

                return {
                    exact: null,
                    sizesCount: count
                };
                """
            )

            if not isinstance(stock_data, dict):
                return {}

            exact = self._safe_int(stock_data.get("exact"), 0)
            if exact > 0:
                return {"stocks": exact}

            sizes_count = self._safe_int(stock_data.get("sizesCount"), 0)
            if sizes_count > 0:
                return {"stocks": sizes_count}

            return {}

        except Exception:
            return {}

        finally:
            self._close_current_tab(original_window)

    def _get_product_sizes_data(self, article, allow_browser_fallback=True):
        article = self._safe_int(article, 0)
        if article <= 0:
            return {}

        # 1) Try recommendation/search endpoint by exact article match.
        try:
            query = quote_plus(f"похожие {article}")
            url = (
                "https://www.wildberries.ru/__internal/u-recom/recom/ru/common/v8/search"
                "?ab_testid=pmb_03&ab_visual_infra=4-ab&appType=1&curr=rub"
                "&dest=-1257786&hide_vflags=4294967296&lang=ru&page=1"
                f"&query={query}&resultset=catalog&spp=30"
            )

            data = self._request_json(url, allow_browser_fallback=allow_browser_fallback)
            product = self._extract_product_from_payload(data, article)
            sizes = self._extract_sizes_from_product(product)
            if sizes:
                return {"sizes": sizes}

        except requests.exceptions.RequestException:
            pass
        except (TypeError, ValueError):
            pass
        except Exception as e:
            print("Ошибка sizes recom:", e)

        # 2) Fallback to detail endpoint by nm.
        try:
            detail_url = (
                "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
                "?appType=1&curr=rub&dest=-1257786&spp=30"
                "&hide_vflags=4294967296&ab_testid=pmb_03&lang=ru"
                f"&nm={article}"
            )
            detail_data = self._request_json(
                detail_url,
                headers={"Referer": "https://www.wildberries.ru/"},
                allow_browser_fallback=allow_browser_fallback,
            )
            detail_product = self._extract_product_from_payload(detail_data, article)
            sizes = self._extract_sizes_from_product(detail_product)
            if sizes:
                return {"sizes": sizes}

        except Exception as e:
            print("Ошибка sizes detail:", e)

        return {}

    def _get_seller_api_warehouses(self):
        if not self.wb_api_token:
            return []

        if self.warehouse_ids_cache is not None:
            return self.warehouse_ids_cache

        if self.wb_warehouse_id:
            self.warehouse_ids_cache = [int(self.wb_warehouse_id)]
            return self.warehouse_ids_cache

        try:
            url = "https://marketplace-api.wildberries.ru/api/v3/warehouses"
            resp = self.api_session.get(url, timeout=10)
            if resp.status_code != 200:
                self.warehouse_ids_cache = []
                return []

            data = resp.json()
            warehouse_ids = []
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    warehouse_id = self._first_non_empty(
                        item.get("id"),
                        item.get("warehouseId"),
                    )
                    warehouse_id = self._safe_int(warehouse_id, 0)
                    if warehouse_id > 0:
                        warehouse_ids.append(warehouse_id)

            self.warehouse_ids_cache = warehouse_ids
            return warehouse_ids

        except Exception as e:
            print("Ошибка warehouses:", e)
            self.warehouse_ids_cache = []
            return []

    def _get_card_chrt_ids(self, article):
        article = self._safe_int(article, 0)
        if not self.wb_api_token or article <= 0:
            return []

        if article in self.card_sizes_cache:
            return self.card_sizes_cache[article]

        try:
            url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
            payload = {
                "settings": {
                    "cursor": {
                        "limit": 100
                    },
                    "filter": {
                        "withPhoto": -1,
                        "textSearch": str(article)
                    }
                }
            }

            resp = self.api_session.post(url, json=payload, timeout=15)
            if resp.status_code != 200:
                self.card_sizes_cache[article] = []
                return []

            data = resp.json()
            cards = data.get("cards", [])
            for card in cards:
                if not isinstance(card, dict):
                    continue

                nm_id = self._safe_int(
                    self._first_non_empty(card.get("nmID"), card.get("nmId")),
                    0,
                )
                if nm_id != article:
                    continue

                chrt_ids = []
                for size_item in card.get("sizes", []):
                    if not isinstance(size_item, dict):
                        continue
                    chrt_id = self._safe_int(
                        self._first_non_empty(size_item.get("chrtID"), size_item.get("chrtId")),
                        0,
                    )
                    if chrt_id > 0 and chrt_id not in chrt_ids:
                        chrt_ids.append(chrt_id)

                self.card_sizes_cache[article] = chrt_ids
                return chrt_ids

            self.card_sizes_cache[article] = []
            return []

        except Exception as e:
            print("Ошибка chrtIds:", e)
            self.card_sizes_cache[article] = []
            return []

    def _get_product_stocks_data(self, article):
        article = self._safe_int(article, 0)
        if article <= 0:
            return {}

        if article in self.stocks_cache:
            return self.stocks_cache[article]

        if not self.wb_api_token:
            return {}

        try:
            chrt_ids = self._get_card_chrt_ids(article)
            warehouse_ids = self._get_seller_api_warehouses()

            if not chrt_ids or not warehouse_ids:
                return {}

            total_amount = 0
            found_any = False

            for warehouse_id in warehouse_ids:
                url = f"https://marketplace-api.wildberries.ru/api/v3/stocks/{warehouse_id}"
                payload = {"chrtIds": chrt_ids}
                resp = self.api_session.post(url, json=payload, timeout=15)

                if resp.status_code != 200:
                    continue

                data = resp.json()
                stocks = data.get("stocks", [])
                if not isinstance(stocks, list):
                    continue

                for stock_item in stocks:
                    if not isinstance(stock_item, dict):
                        continue
                    amount = self._safe_int(stock_item.get("amount"), 0)
                    total_amount += amount
                    found_any = True

            if not found_any:
                return {}

            stock_data = {"stocks": total_amount}
            self.stocks_cache[article] = stock_data
            return stock_data

        except Exception as e:
            print("Ошибка stocks:", e)
            return {}

    def _get_product_detail_data(self, article, product_url=None, detail_product=None, allow_browser_fallback=True):
        try:
            if isinstance(detail_product, dict):
                return self._parse_product_detail_data(detail_product)

            url = (
                "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
                "?appType=1&curr=rub&dest=-1257786&spp=30"
                "&hide_vflags=4294967296&ab_testid=pmb_03&lang=ru"
                f"&nm={article}"
            )

            headers = {
                "Referer": product_url or "https://www.wildberries.ru/",
                "X-Requested-With": "XMLHttpRequest",
            }
            data = self._request_json(url, headers=headers, allow_browser_fallback=allow_browser_fallback)
            product = self._extract_product_from_payload(data, article)
            return self._parse_product_detail_data(product)

        except requests.exceptions.RequestException:
            return {}
        except (TypeError, ValueError):
            return {}
        except Exception as e:
            print("Ошибка detail:", e)
            return {}

    # -----------------------------
    # получение продавца
    # -----------------------------

    def _get_supplier_info(self, supplier_id):
        supplier_id = str(supplier_id)

        if supplier_id in self.suppliers_cache:
            return self.suppliers_cache[supplier_id]

        try:
            url = f"https://static-basket-01.wbbasket.ru/vol0/data/supplier-by-id/{supplier_id}.json"
            data = self._request_json(url, allow_browser_fallback=False)
            if not data:
                return {}

            supplier_data = self._normalize_supplier_data(
                supplier_id=supplier_id,
                supplier_name=(
                    data.get("trademark")
                    or data.get("supplierFullName")
                    or data.get("supplierName")
                    or data.get("name")
                ),
            )

            if supplier_data:
                self.suppliers_cache[supplier_id] = supplier_data

            return supplier_data

        except requests.exceptions.RequestException:
            return {}

        except Exception as e:
            print("Ошибка supplier:", e)
            return {}

    def _get_supplier_from_catalog(self, supplier_id):
        supplier_id = str(supplier_id)

        if supplier_id in self.suppliers_cache:
            return self.suppliers_cache[supplier_id]

        try:
            url = (
                "https://www.wildberries.ru/__internal/u-catalog/sellers/v4/catalog"
                f"?supplier={supplier_id}"
            )

            data = self._request_json(url, allow_browser_fallback=False)
            products = data.get("products", [])

            if not products:
                return {}

            product = products[0]
            supplier_data = self._normalize_supplier_data(
                supplier_id=(
                    product.get("supplierId")
                    or product.get("supplier_id")
                    or supplier_id
                ),
                supplier_name=(
                    product.get("supplier")
                    or product.get("supplierName")
                    or product.get("supplierFullName")
                ),
                supplier_link=product.get("supplierLink"),
            )

            if supplier_data:
                self.suppliers_cache[supplier_id] = supplier_data

            return supplier_data

        except requests.exceptions.RequestException:
            return {}

        except Exception as e:
            print("Ошибка catalog supplier:", e)
            return {}

    def _get_supplier_from_product_page(self, product_url):
        if not product_url:
            return {}

        original_window = self._open_in_new_tab(product_url)
        if not original_window:
            return {}

        try:
            anchor = self.driver.find_element(By.CSS_SELECTOR, "a[href*='/seller/']")
            supplier_link = anchor.get_attribute("href")
            supplier_name = anchor.text.strip()

            supplier_data = self._normalize_supplier_data(
                supplier_name=supplier_name,
                supplier_link=supplier_link,
            )
            supplier_id = supplier_data.get("supplier_id")

            if supplier_id:
                self.suppliers_cache[supplier_id] = supplier_data

            return supplier_data

        except Exception:
            return {}

        finally:
            self._close_current_tab(original_window)




