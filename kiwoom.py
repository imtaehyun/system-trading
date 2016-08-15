# -*- coding: utf-8 -*-
import sys
import logging
import logging.config
from collections import defaultdict
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QAxContainer import QAxWidget
import code as CODE
from database import Database

SCREEN_CONDITION_SEARCH = '0001'

SCREEN_BUY_STOCK = '0010'
SCREEN_SELL_STOCK = '0011'

logger = logging.getLogger(__name__)
logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)-15s] (%(filename)s:%(lineno)d) %(name)s:%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },

        'file_handler': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'filename': './logs/trading-' + datetime.now().strftime("%Y%m%d") + '.log',
            'encoding': 'utf-8'
        },

        "real_handler": {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'standard',
            'filename': './logs/real-' + datetime.now().strftime("%Y%m%d") + '.log',
            'encoding': 'utf-8'
        }
    },
    'loggers': {
        'real': {
            'handlers': ["real_handler"],
            'level': 'DEBUG',
            'propagate': True
        }
    },

    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file_handler"]
    }
})

realDataLogger = logging.getLogger("real")


class TradingWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.user = None

        infinite_dict = lambda: defaultdict(infinite_dict)
        self.watch = infinite_dict()
        self.used = []

        # DB 연결
        self.db = Database()

        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")

        # Event Handler 등록
        self.kiwoom.OnEventConnect[int].connect(self.OnEventConnect)
        self.kiwoom.OnReceiveTrData[str, str, str, str, str, int, str, str, str].connect(self.OnReceiveTrData)
        self.kiwoom.OnReceiveRealData[str, str, str].connect(self.OnReceiveRealData)
        self.kiwoom.OnReceiveMsg[str, str, str, str].connect(self.OnReceiveMsg)
        self.kiwoom.OnReceiveChejanData[str, int, str].connect(self.OnReceiveChejanData)

        # 조건검색 관련 Event Handler
        self.kiwoom.OnReceiveRealCondition[str, str, str, str].connect(self.OnReceiveRealCondition)
        self.kiwoom.OnReceiveTrCondition[str, str, str, int, int].connect(self.OnReceiveTrCondition)
        self.kiwoom.OnReceiveConditionVer[int, str].connect(self.OnReceiveConditionVer)

        self.login()

    def login(self):
        """키움증권 로그인
        CommConnect()
        :return 0 - 성공, 음수값은 실패
        로그인이 성공하거나 실패하는 경우 OnEventConnect 이벤트가 발생하고 이벤트의 인자 값으로 로그인 성공 여부를 알 수 있다.
        """
        connect_result = self.kiwoom.CommConnect()
        if connect_result == 0:
            logger.debug("로그인 윈도우 실행 성공")
        else:
            logger.debug("로그인 윈도우 실행 실패")

    def get_login_info(self):
        """로그인 정보를 반환

        - “ACCOUNT_CNT” – 전체 계좌 개수를 반환한다.
        - "ACCNO" – 전체 계좌를 반환한다. 계좌별 구분은 ‘;’이다.
        - “USER_ID” - 사용자 ID를 반환한다.
        - “USER_NAME” – 사용자명을 반환한다.
        - “KEY_BSECGB” – 키보드보안 해지여부. 0:정상, 1:해지
        - “FIREW_SECGB” – 방화벽 설정 여부. 0:미설정, 1:설정, 2:해지
        """
        account_cnt = self.kiwoom.GetLoginInfo("ACCOUNT_CNT")
        ret_accno = self.kiwoom.GetLoginInfo("ACCNO")
        user_id = self.kiwoom.GetLoginInfo("USER_ID")
        user_name = self.kiwoom.GetLoginInfo("USER_NAME")
        key_bsecgb = self.kiwoom.GetLoginInfo("KEY_BSECGB")
        firew_secgb = self.kiwoom.GetLoginInfo("FIREW_SECGB")

        # 계좌는 복수개이기때문에 ; 로 split
        accno = ret_accno.split(';')[:-1]

        login_info = dict(account_cnt=account_cnt, accno=accno, user_id=user_id, user_name=user_name,
                          key_bsecgb=key_bsecgb, firew_secgb=firew_secgb)
        logger.info('login_info: %s', login_info)

        return login_info

    def get_connect_state(self):
        """현재접속상태를 반환"""
        connect_state = self.kiwoom.GetConnectState()
        if connect_state == 0:
            print("미연결")
        elif connect_state == 1:
            print("연결완료")

    def OnEventConnect(self, nErrCode):
        """OnEventConnect: 서버 접속 관련 이벤트
        입력값
        LONG nErrCode : 에러 코드

        비고
        nErrCode가 0이면 로그인 성공, 음수면 실패
        음수인 경우는 에러 코드 참조
        """
        logger.debug('OnEventConnect: %s', dict(nErrCode=nErrCode))

        if nErrCode == 0:
            logger.info("로그인 성공")

            self.user = self.get_login_info()

            # 장시작시간 실세간 추가
            # self.kiwoom.SetRealReg("REAL002", "", "215;20;214;", "0")

            # 조건검색 시작
            self.kiwoom.GetConditionLoad()

        else:
            logger.info("로그인 실패: %s" + dict(nErrCode=nErrCode))

    def OnReceiveTrData(self, sScrNo, sRQName, sTrCode, sRecordName, sPreNext, nDataLength, sErrorCode, sMessage,
                        sSplmMsg):
        """OnReceiveTrData: 서버통신 후 데이터를 받은 시점을 알려준다.
        입력값
        sScrNo . 화면번호
        sRQName . 사용자구분 명
        sTrCode . Tran 명
        sRecordName . Record 명
        sPreNext . 연속조회 유무

        비고
        sRQName . CommRqData의 sRQName과 매핑되는 이름이다.
        sTrCode . CommRqData의 sTrCode과 매핑되는 이름이다.
        """
        logger.debug('OnReceiveTrData: %s',
              dict(sScrNo=sScrNo, sRQName=sRQName, sTrCode=sTrCode, sRecordName=sRecordName, sPreNext=sPreNext,
                   nDataLength=nDataLength, sErrorCode=sErrorCode, sMessage=sMessage, sSplmMsg=sSplmMsg))

        count = self.kiwoom.GetRepeatCnt(sTrCode, sRQName)
        for i in range(0, count):
            self.kiwoom.GetCommData(sTrCode, sRQName, i, )


    def OnReceiveRealData(self, sJongmokCode, sRealType, sRealData):
        """OnReceiveRealData: 실시간데이터를 받은 시점을 알려준다.

        입력값
        sJongmokCode . 종목코드
        sRealType . 리얼타입
        sRealData . 실시간 데이터전문
        """
        logger.debug('OnReceiveRealData: %s', dict(sJongmokCode=sJongmokCode, sRealType=sRealType, sRealData=sRealData))
        # if sRealType == "주식체결":
        #     # logger.debug("code: %s, real_data: %s", sJongmokCode, sRealData)
        #     # logger.debug("종목: %s, current: %s", sJongmokCode, sRealData.split('\t')[1].replace('+', ''))
        #     price = int(sRealData.split('\t')[1].replace('+', '').replace('-', ''))  # 현재가
        #     sell = int(sRealData.split('\t')[4].replace('+', '').replace('-', ''))  # (최우선) 매도호가
        #     buy = int(sRealData.split('\t')[5].replace('+', '').replace('-', ''))  # (최우선) 매수호가
        #     # self.printData(sJongmokCode, sRealData.split('\t'))
        #
        #     self.brain(dict(code=sJongmokCode, price=price, sell=sell, buy=buy))

    def printData(self, jongmok, data):
        logger.debug("종목: %s", jongmok)
        # logger.debug("체결시간: %s", data[0])
        logger.debug("현재가: %s", data[1])
        # logger.debug("전일대비: %s", data[2])
        logger.debug("등락률: %s", data[3])
        logger.debug("매도 / 매수: %s / %s", data[4], data[5])
        logger.debug("거래량: %s", data[6])
        logger.debug("누적거래량: %s", data[7])
        logger.debug("누적거래대금: %s", data[8])
        logger.debug("시고저: %s / %s / %s", data[9], data[10], data[11])
        logger.debug("체결강도: %s", data[18])
        logger.debug("                     ")

    def brain(self, data):
        status = 2
        diff = False

        # 추적리스트에서 빠졌는데 다시 들어오지 않도록 방어로직
        if data['code'] in self.used:
            return

        # watchList에 데이터가 없으면 구매
        if not self.watch[data['code']]:
            status = 1
            self.watch[data['code']]['buy'] = data['price']

        if self.watch[data['code']]['current'] != data['price']:
            diff = True

        # 현재가
        self.watch[data['code']]['current'] = data['price']

        # 고가
        if not self.watch[data['code']]['high'] or self.watch[data['code']]['current'] > self.watch[data['code']]['high']:
            self.watch[data['code']]['high'] = data['price']

        # 매도시점 1. 최고가에서 2% 빠지면 매도
        if (self.watch[data['code']]['high'] - self.watch[data['code']]['current']) / self.watch[data['code']]['high'] >= 0.02:
            status = 3

        # 매도시점 2. 매수가에서 4%로 수익나면 매도
        if (self.watch[data['code']]['current'] - self.watch[data['code']]['buy']) / self.watch[data['code']]['current'] >= 0.04:
            status = 3

        if status == 1:
            self.sendOrder(data['code'], 100)
            logger.info('[1. 매수] 종목: %s, 매수가: %s', data['code'], data['price'])
        elif status == 3:
            self.sendSell(data['code'], 100)
            logger.info('[3. 매도] 종목: %s, 현재가: %s, 고가: %s, 매수가: %s, 수익률: %s', data['code'], data['price'],
                         self.watch[data['code']]['high'], self.watch[data['code']]['buy'],
                         (self.watch[data['code']]['current'] - self.watch[data['code']]['buy']) /
                         self.watch[data['code']]['buy'])

            # 추적리스트에서 삭제
            del self.watch[data['code']]

            # 실시간 해제
            self.kiwoom.SetRealRemove("REAL001", data['code'])

            self.used.append(data['code'])

        else:
            if diff:
                # pass
                logger.debug('[2. 추적] 종목: %s, 현재가: %s, 고가: %s, 매수가: %s, 몇프로: %s', data['code'], data['price'],
                        self.watch[data['code']]['high'], self.watch[data['code']]['buy'],
                        (self.watch[data['code']]['high'] - self.watch[data['code']]['current']) / self.watch[data['code']]['high'])

    def sendOrder(self, code, qty):
        """주식 매수, 시장가 매수"""
        req_name = "ORD_" + datetime.now().strftime("%Y%m%d%H%M%S")
        screen_no = "0001"
        acct_no = self.user['accno'][0]
        order_type = 1  # 신규매수
        hoga_gubun = "03"  # 시장가

        self.kiwoom.SendOrder(req_name, screen_no, acct_no, order_type, code, qty, 0, hoga_gubun, "")

    def sendSell(self, code, qty):
        """주식 매도, 시장가 매도"""
        req_name = "ORD_" + datetime.now().strftime("%Y%m%d%H%M%S")
        screen_no = "0001"
        acct_no = self.user['accno'][0]
        order_type = 2  # 신규매도
        hoga_gubun = "03"  # 시장가

        self.kiwoom.SendOrder(req_name, screen_no, acct_no, order_type, code, qty, 0, hoga_gubun, "")

    def OnReceiveMsg(self, sScrNo, sRQName, sTrCode, sMsg):
        """OnReceiveMsg: 서버통신 후 메시지를 받은 시점을 알려준다.
        입력값
        sScrNo . 화면번호
        sRQName . 사용자구분 명
        sTrCode . Tran 명
        sMsg . 서버메시지

        비고
        sScrNo . CommRqData의 sScrNo와 매핑된다.
        sRQName . CommRqData의 sRQName 와 매핑된다.
        sTrCode . CommRqData의 sTrCode 와 매핑된다.
        """
        logger.debug("-----------------------")
        logger.debug("OnReceiveMsg: %s", dict(sScrNo=sScrNo, sRQName=sRQName, sTrCode=sTrCode, sMsg=sMsg))
        logger.debug("화면번호: %s", sScrNo)
        logger.debug("사용자구분명: %s", sRQName)
        logger.debug("Tran 명: %s", sTrCode)
        logger.debug("서버메시지: %s", sMsg)
        logger.debug("-----------------------")

    def OnReceiveChejanData(self, sGubun, nItemCnt, sFidList):
        """OnReceiveChejanData: 체결데이터를 받은 시점을 알려준다.
        입력값
        sGubun . 체결구분
        nItemCnt - 아이템갯수
        sFidList . 데이터리스트

        비고
        sGubun . 0:주문체결통보, 1:잔고통보, 3:특이신호
        sFidList . 데이터 구분은 ‘;’ 이다.
        """
        try:
            gubun = {"0": "주문체결통보", "1": "잔고통보", "3": "특이신호"}

            logger.debug("-----------------------")
            logger.debug("OnReceiveChejanData: %s", dict(sGubun=sGubun, nItemCnt=nItemCnt, sFidList=sFidList))
            logger.debug("체결구분: %s", gubun[sGubun])

            data = []
            for fid in sFidList.split(";"):
                fid_name = CODE.get_fid_msg(fid)
                fid_data = self.kiwoom.GetChejanData(int(fid))
                logger.debug("%s: %s", fid_name, fid_data)
                data.append(fid_data)
            logger.debug("-----------------------")

            if sGubun == "0" and data[5] == "체결":
                # 주문체결통보
                self.db.insert_ord_data(data)

        except Exception as e:
            logger.exception(e, exc_info=True)

    def OnReceiveRealCondition(self, strCode, strType, strConditionName, strConditionIndex):
        """OnReceiveRealCondition: 조건검색 실시간 편입,이탈 종목을 받을 시점을 알려준다.
        입력값
        LPCTSTR strCode : 종목코드
        LPCTSTR strType : 편입(“I”), 이탈(“D”)
        LPCTSTR strConditionName : 조건명
        LPCTSTR strConditionIndex : 조건명 인덱스

        비고
        strConditionName에 해당하는 종목이 실시간으로 들어옴.
        strType으로 편입된 종목인지 이탈된 종목인지 구분한다.
        """
        # logger.debug('OnReceiveRealCondition: %s', dict(strCode=strCode, strType=strType, strConditionName=strConditionName,
                                                # strConditionIndex=strConditionIndex))
        if strType == "I":  # and len(self.watch) <= 10:
            self.kiwoom.SetRealReg("REAL001", strCode, "10;", "1")

    def OnReceiveTrCondition(self, sScrNo, strCodeList, strConditionName, nIndex, nNext):
        """OnReceiveTrCondition: 조건검색 조회응답으로 종목리스트를 구분자(“;”)로 붙어서 받는 시점.
        입력값
        LPCTSTR sScrNo : 종목코드
        LPCTSTR strCodeList : 종목리스트(“;”로 구분)
        LPCTSTR strConditionName : 조건명
        int nIndex : 조건명 인덱스
        int nNext : 연속조회(2:연속조회, 0:연속조회없음)
        """
        logger.debug('OnReceiveTrCondition: %s',
              dict(sScrNo=sScrNo, strCodeList=strCodeList, strConditionName=strConditionName, nIndex=nIndex,
                   nNext=nNext))
        try:
            self.kiwoom.SetRealReg("REAL001", strCodeList, "10;", "0")
        except Exception as e:
            logger.exception(e)

    def OnReceiveConditionVer(self, lRet, sMsg):
        """로컬에 사용자 조건식 저장 성공 여부를 확인하는 시점
        long lRet : 사용자 조건식 저장 성공여부 (1: 성공, 나머지 실패)
        """
        try:
            logger.debug('OnReceiveConditionVer: %s', dict(lRet=lRet, sMsg=sMsg))

            if lRet == 1:
                condition_list = self.kiwoom.GetConditionNameList()
                logger.info("조건검색 조회성공: %s", condition_list)

                for condition in condition_list.split(';')[:-1]:
                    index = condition.split('^')[0]
                    name = condition.split('^')[1]

                    # 실시간 조건검색 등록
                    self.kiwoom.SendCondition(SCREEN_CONDITION_SEARCH, name, int(index), 1)
            else:
                logger.error("조건검색 조회실패: %s", dict(lRet=lRet, sMsg=sMsg))
        except Exception as e:
            logger.exception(e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tradingWindow = TradingWindow()
    tradingWindow.show()
    app.exec_()
