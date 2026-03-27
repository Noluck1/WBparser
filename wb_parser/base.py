import os
import random
import threading
import time

import requests
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium_stealth import stealth


class BaseParserMixin:

    def __init__(self):
        self.driver = self._init_driver()
        self.driver_lock = threading.RLock()
        self.suppliers_cache = {}
        self.card_sizes_cache = {}
        self.stocks_cache = {}
        self.warehouse_ids_cache = None
        self.page_data_cache = {}
        self.wb_api_token = os.getenv("WB_API_TOKEN", "").strip()
        self.wb_warehouse_id = os.getenv("WB_WAREHOUSE_ID", "").strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })
        self.api_session = requests.Session()
        if self.wb_api_token:
            self.api_session.headers.update({
                "Authorization": self.wb_api_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    def _init_driver(self):
        options = Options()

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=ru-RU")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        driver = webdriver.Chrome(options=options)

        stealth(
            driver,
            languages=["ru-RU", "ru"],
            vendor="Google Inc.",
            platform="Win32",
        )

        return driver

    def warmup(self):
        with self.driver_lock:
            if not self._ensure_driver_window():
                return
            self.driver.get("https://www.wildberries.ru")
        time.sleep(5)

    def _human_behavior(self):
        time.sleep(random.uniform(0.6, 1.2))
        with self.driver_lock:
            if not self._ensure_driver_window():
                return
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(0.4, 0.8))

    def _parse_list(self):
        with self.driver_lock:
            if not self._ensure_driver_window():
                return []
            items = self.driver.find_elements(By.CLASS_NAME, "product-card__wrapper")

            results = []
            seen_articles = set()

            for item in items:
                try:
                    name = item.find_element(By.CLASS_NAME, "product-card__name").text

                    price = ""
                    try:
                        price = item.find_element(By.CLASS_NAME, "price__lower-price").text
                    except Exception:
                        pass

                    link = item.find_element(By.TAG_NAME, "a").get_attribute("href")
                    if not link or "/catalog/" not in link:
                        continue

                    article = link.split("/catalog/")[1].split("/")[0]
                    if not article.isdigit() or article in seen_articles:
                        continue

                    seen_articles.add(article)

                    results.append({
                        "name": name,
                        "price": price,
                        "url": link,
                        "article": article,
                    })

                except Exception:
                    continue

            return results

    def _collect_search_results(self, limit):
        previous_count = 0

        for _ in range(8):
            products = self._parse_list()
            if len(products) >= limit:
                return products[:limit]

            if len(products) == previous_count:
                break

            previous_count = len(products)
            with self.driver_lock:
                if not self._ensure_driver_window():
                    break
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.6)

        return self._parse_list()[:limit]

    def _open_in_new_tab(self, url, pause=2):
        with self.driver_lock:
            original_window = self._ensure_driver_window()
            if not original_window:
                return None

            try:
                self.driver.switch_to.new_window("tab")
                self.driver.get(url)
                time.sleep(pause)
                return original_window
            except Exception:
                try:
                    self.driver.switch_to.window(original_window)
                except Exception:
                    pass
                return None

    def _close_current_tab(self, original_window):
        with self.driver_lock:
            try:
                handles = self.driver.window_handles
            except Exception:
                return

            try:
                if len(handles) > 1:
                    self.driver.close()
            except Exception:
                pass

            if original_window:
                try:
                    self.driver.switch_to.window(original_window)
                    return
                except Exception:
                    pass

            try:
                remaining_handles = self.driver.window_handles
                if remaining_handles:
                    self.driver.switch_to.window(remaining_handles[0])
            except Exception:
                pass

    def _ensure_driver_window(self):
        try:
            handles = self.driver.window_handles
        except Exception:
            return self._reset_driver()

        if not handles:
            return self._reset_driver()

        try:
            current_handle = self.driver.current_window_handle
            if current_handle in handles:
                return current_handle
        except Exception:
            pass

        for handle in handles:
            try:
                self.driver.switch_to.window(handle)
                return handle
            except Exception:
                continue

        return self._reset_driver()

    def _reset_driver(self):
        try:
            self.driver.quit()
        except Exception:
            pass

        try:
            self.driver = self._init_driver()
            return self.driver.current_window_handle
        except WebDriverException:
            return None

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
