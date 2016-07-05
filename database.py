import logging
import sqlite3

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db = sqlite3.connect("data/trading.db")
        self.cursor = self.db.cursor()
        logger.info("db connection init")

    def __del__(self):
        self.cursor.close()
        self.db.close()
        logger.info("db connection close")

    def add_condition_stock_item(self, stock_codes):
        """조건검색결과 종목 추가"""
        self.cursor.executemany("INSERT INTO condition_stock (stock_code) values (?)", stock_codes)
        self.db.commit()

    def del_condition_stock_item(self, stock_code):
        """조건검색결과 종목 제거"""
        self.cursor.execute("UPDATE condition_stock SET use_yn = 'N', mod_dts = datetime('now', 'localtime') WHERE stock_code = ?", (stock_code,))
        self.db.commit()
