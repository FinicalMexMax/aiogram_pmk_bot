import json
import logging
from typing import Any, Dict, List


class OrderManager:
    def __init__(self, pool):
        self.pool = pool

    