#! /usr/bin/env python                                                                   
# -*- coding: utf-8 -*-

import pjsua as pj
#from abc import ABCMeta, abstractmethod
import abc
import math
import subprocess
import time
import wave



# セッティング

LOG_LEVEL = 3
PORT = 5060

# セッティングここまで



class PhoneCallback(pj.AccountCallback, pj.CallCallback):

    def __init__(self, func, account=None, call=None):
        pj.AccountCallback.__init__(self, account)
        pj.CallCallback.__init__(self, call)

        # FunctionBaseクラスを継承していないクラスの場合はエラー
        assert isinstance(func, FunctionBase)

        self.func = func
 
    """
    Override(pj.AccountCallback)
    Notification on incoming call
    """
    def on_incoming_call(self, call):
        global current_call 

        # 電話中
        if current_call:
            call.answer(486, "Busy")
            return
            
        print "Incoming call from ", call.info().remote_uri

        current_call = call

        current_call.set_callback(self)
        current_call.answer(180)        
        current_call.answer(200)



    def on_dtmf_digit(self, digits):
        """
        Override(pj.CallCallback)
        Notification on incoming DTMF digits.
        """

#        print "INCOMING DTMF:%s" % digits
        try:
            self.func.update(dtmf=digits)
        except Exception, e:
            print "on_dtmf_digit: ", e


    def on_state(self):
        """
        Override(pj.CallCallback)
        Notification when call state has changed
        """
        global current_call
        global PROCESSING

        print "Call with", self.call.info().remote_uri,
        print "is", self.call.info().state_text,
        print "last code =", self.call.info().last_code, 
        print "(" + self.call.info().last_reason + ")"
        
        if self.call.info().state == pj.CallState.DISCONNECTED:
            current_call = None
            print 'Current call is', current_call
            PROCESSING = False

    def on_media_state(self):
        """
        Override(pj.CallCallback)
        Notification when call's media state has changed.
        """
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
#            pj.Lib.instance().conf_connect(call_slot, 0)
#            pj.Lib.instance().conf_connect(0, call_slot)
            print "Media is now active"
            
            # 実行
            self.func.update()

        else:
            print "Media is inactive"

class FunctionBase():
    """
    機能のベースクラス。
    抽象クラス。
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def update(self, dtmf=-1):
        assert 0, "update function must be defined!"

class StateBase():
    """
    ステータスのベースクラス
    抽象クラス
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def enter(self):
        assert 0, "enter function must be defined!"

    @abc.abstractmethod
    def execute(self, dtmf=-1):
        assert 0, "execute function must be defined!"

    @abc.abstractmethod
    def exit(self):
        assert 0, "exit function must be defined!"
    
class Func_AnsweringMachine(FunctionBase):

    prevState = None
    currentState = None

    AQUESTALKPI_PATH = "/home/pi/aquestalkpi/AquesTalkPi"
    TMP_DIR = "/tmp/"
    TMPFILE_NAME = "aqout.wav"
    TMPFILE_PATH = TMP_DIR + TMPFILE_NAME

    def __init__(self):
        self.currentState = self.State_Intro(self)

    # Override
    def update(self, dtmf=-1):
#        print "DTMF:%s" % dtmf
        # Trap
        assert isinstance(self.currentState, StateBase), "StateBaseクラスじゃないよ"
        # Fire
        self.currentState.execute(dtmf)

    def changeState(self, state):
        print "ChangeState()"
        assert isinstance(state, StateBase), "StateBaseクラスじゃないよ"

        self.currentState.exit()

        self.currentState = state

        self.currentState.enter()


    def createWavfile(self, text):
        # textを読んだ音声データを生成
        try:
            subprocess.check_call([self.AQUESTALKPI_PATH, text, "-o", self.TMPFILE_PATH])
        except subprocess.CalledProcessError, (p):
            print 'subprocess.CalledProcessError: cmd:%s returncode:%s' % (p.cmd, p.returncode)
            return 0

        # できたWavファイルを解析。
        try:
            wr = wave.open(self.TMPFILE_PATH, "r")
        except wave.Error, e:
            print "Error open wavfile", e
            return 0

        print "長さ（秒）:", math.ceil(float(wr.getnframes()) / wr.getframerate())
        
        # 小数点切り上げした値を返す
        return math.ceil(float(wr.getnframes()) / wr.getframerate())


    def speak(self, text):
        global current_call

        # テキストが空の場合はリターン
        if text == None:
            return -1

        # 電話が切れている場合はリターン
        if current_call == None:
            return -1

        # textを音声に変換したwavファイルを作成。
        if self.createWavfile(text) == 0:
            return -1     

        # 再生
        try: 
            self.player = pj.Lib.instance().create_player(self.TMPFILE_PATH, False)
        except Exception, e:
            print "Error playing greeting", e
            return -1
        
        try: 
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_connect(player_slot, call_slot)
        except Exception, e:
            print "An error occured.", e
            return -1
        
        # 音声データを削除
        try:
            subprocess.check_call(["rm", self.TMPFILE_PATH])
        except subprocess.CalledProcessError, (p):
            print 'subprocess.CalledProcessError: cmd:%s returncode:%s' % (p.cmd, p.returncode)
            return -1

        return self.player


    class State_Intro(StateBase):
        func = None
        player = None
        
        def __init__(self, func):
            self.func = func

        def enter(self):
            print "State_Intro enter()"


        def execute(self, dtmf=-1):
            print "State_Intro execute() %s" % dtmf

            if dtmf == -1:
                msg = "こんにちは。CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。"

                self.player = self.func.speak(msg)

            elif dtmf == "1":
                self.func.changeState(self.func.State_CPUTemp(self.func))

        def exit(self):
            print "State_Intro exit()"

            global current_call

            # 回線が切断されている場合はリターン
            if current_call == None:
                print "切断されているわよ"
                return

            # 音声の再生に使ったプレイヤーの後処理をする
            player_slot = pj.Lib.instance().player_get_slot(self.player)
            call_slot = current_call.info().conf_slot
            pj.Lib.instance().conf_disconnect(player_slot, call_slot)
            pj.Lib.instance().player_destroy(self.player)


    class State_CPUTemp(StateBase):
        """
        「ただいまのCPU温度はXX度です」と発話する。
        """
        func = None
        player = None

        def __init__(self, func):
            self.func = func
            
        # Override
        def enter(self):
            print "State_CPUTemp enter()"

            temp = self.getCPUTemp()

            if temp != "":
                msg = "ただいまのCPU温度は%s度です。" % temp
            else:
                msg = "CPU温度の取得に失敗しました。"

            self.player = self.func.speak(msg)

        # Override
        def execute(self, dtmf=-1):
            print "State_CPUTemp execute() %s" % dtmf

            if dtmf == "0":
                self.func.changeState(self.func.State_Intro(self.func))
            elif dtmf == "1":
                self.func.changeState(self.func.State_CPUTemp(self.func))
                
        # Override
        def exit(self):
            print "State_CPUTemp exit()"

            global current_call

            # 回線が切断されている場合はリターン
            if current_call == None:
                print "切断されているわよ"
                return

            # 音声の再生に使ったプレイヤーの後処理をする
            player_slot = pj.Lib.instance().player_get_slot(self.player)
            call_slot = current_call.info().conf_slot
            pj.Lib.instance().conf_disconnect(player_slot, call_slot)
            pj.Lib.instance().player_destroy(self.player)


        def getCPUTemp(self):
            """
            CPU温度を取得して文字列で返す
            """
            try:
                self.s = subprocess.check_output(["/opt/vc/bin/vcgencmd","measure_temp"])
                self.val = str(self.s.split('=')[1][:-3])
            except:
                self.val = ""

            return self.val


# Logging callback
def log_cb(level, str, len):
    print str,

if __name__ == "__main__":
    current_call = None
    PROCESSING = False

    #
    lib = pj.Lib()

    try:
        lib.init(log_cfg = pj.LogConfig(level=LOG_LEVEL, callback=log_cb))

        transport = lib.create_transport(pj.TransportType.UDP, pj.TransportConfig(PORT))
        print "\nListening on", transport.info().host, 
        print "port", transport.info().port, "\n"

        #
        lib.set_null_snd_dev()

        # Start the library
        lib.start()
        PROCESSING = True

        # Create local account
        acc = lib.create_account_for_transport(transport, cb=PhoneCallback(Func_AnsweringMachine()))

        while(PROCESSING):
            pass

        transport = None
        acc.delete()
        acc = None
        lib.destroy()
        lib = None

    except pj.Error, e:
        print "Exception: %s" % e
        lib.destory()
        lib = None




