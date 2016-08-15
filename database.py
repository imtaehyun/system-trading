import logging
import sqlite3

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

    def insert_ord_data(self, data):
        """주문결과 저장"""
        sql = """
        INSERT INTO ORD (
          ord_no
          , stock_code
          , stock_name
          , ord_type
          , contract_time
          , contract_no
          , price
          , qty
          , charge
          , tax
        ) VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        param = (data[1], data[3], data[6], data[14], data[15], data[16], data[17], data[18], data[24], data[25])
        logger.debug("INSERT ORD: %s", param)
        self.cursor.execute(sql, param)
        self.db.commit()

