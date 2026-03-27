from .api import ApiMixin
from .base import BaseParserMixin
from .exporter import ExportMixin
from .product import ProductMixin
from .search import SearchMixin
from .utils import UtilsMixin


class WBParser(SearchMixin, ExportMixin, ProductMixin, ApiMixin, UtilsMixin, BaseParserMixin):
    pass
