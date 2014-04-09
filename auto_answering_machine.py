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
            self.func.changeState(self.func.State_Intro(self.func))

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
        
        # 小数点切り上げしたファイルの長さ(秒)を返す
        return math.ceil(float(wr.getnframes()) / wr.getframerate())


    def speak(self, text):
        global current_call

        # テキストが空の場合はリターン
        if text == None:
            return -1

        """
        # 電話が切れている場合はリターン
        if current_call == None:
            return -1
        """

        # textを音声に変換したwavファイルを作成。
        if self.createWavfile(text) == 0:
            return -1     

        # 再生
        try: 
            player = pj.Lib.instance().create_player(self.TMPFILE_PATH, False)
        except Exception, e:
            print "Error playing greeting", e
            return -1
        
        try: 
            #if self.player != -1:
            player_slot = pj.Lib.instance().player_get_slot(player)
            call_slot = current_call.info().conf_slot
            pj.Lib.instance().conf_connect(player_slot, call_slot)
        except Exception, e:
            print "An error occured.", e
            return player
        
        # 音声データを削除
        try:
            subprocess.check_call(["rm", self.TMPFILE_PATH])
        except subprocess.CalledProcessError, (p):
            print 'subprocess.CalledProcessError: cmd:%s returncode:%s' % (p.cmd, p.returncode)

        return player


    class State_Intro(StateBase):
        """
        自己紹介文を発話する。
        入力されたDTMFにより、ステートを変化させる。
        """
        def __init__(self, func):
            self.func = func
            self.player = -1

        def enter(self):
            print "State_Intro enter()"
            msg = "こんにちは。こちらはラズベリーパイです。CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は0を入力してください。"
            self.player = self.func.speak(msg)

        def execute(self, dtmf=-1):
            print "State_Intro execute() %s" % dtmf

            if dtmf == "1":
                # CPU温度ステートに変更
                self.func.changeState(self.func.State_CPUTemp(self.func))
            elif dtmf == "2":
                # メモリ状況ステートに変更
                self.func.changeState(self.func.State_MemState(self.func))
            elif dtmf == "3":
                # 起動時間ステートに変更
                self.func.changeState(self.func.State_Uptime(self.func))

        def exit(self):
            print "State_Intro exit()"

            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_disconnect(player_slot, call_slot)
                pj.Lib.instance().player_destroy(self.player)

    class State_Help(StateBase):
        """
        使い方の説明を発話する。
        """
        def __init__(self, func):
            self.func = func
            self.player = -1

        def enter(self):
            print "State_Help enter()"
            msg = "CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は0を入力してください。"
            self.player = self.func.speak(msg)

        def execute(self, dtmf=-1):
            print "State_Help execute() %s" % dtmf

            if dtmf == "1":
                # CPU温度ステートに変更
                self.func.changeState(self.func.State_CPUTemp(self.func))
            elif dtmf == "2":
                # メモリ状況ステートに変更
                self.func.changeState(self.func.State_MemState(self.func))
            elif dtmf == "3":
                # 起動時間ステートに変更
                self.func.changeState(self.func.State_Uptime(self.func))

        def exit(self):
            print "State_Help exit()"

            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_disconnect(player_slot, call_slot)
                pj.Lib.instance().player_destroy(self.player)


    class State_CPUTemp(StateBase):
        """
        「ただいまのCPU温度はXX度です」と発話する。
        """
        def __init__(self, func):
            self.func = func
            self.player = -1
            
        # Override
        def enter(self):
            print "State_CPUTemp enter()"
            
            # CPU温度を取得
            temp = self.getCPUTemp()

            # 発話内容を作成。
            if temp != "":
                msg = "ただいまのCPU温度は%s度です。" % temp
            else:
                msg = "CPU温度の取得に失敗しました。"

            # 発話
            self.player = self.func.speak(msg)

        # Override
        def execute(self, dtmf=-1):
            print "State_CPUTemp execute() %s" % dtmf

            if dtmf == "0":
                # イントロステートに変更
                self.func.changeState(self.func.State_Help(self.func))
            elif dtmf == "1":
                # CPU温度ステートに変更
                self.func.changeState(self.func.State_CPUTemp(self.func))
            elif dtmf == "2":
                # メモリ状況ステートに変更
                self.func.changeState(self.func.State_MemState(self.func))
            elif dtmf == "3":
                # 起動時間ステートに変更
                self.func.changeState(self.func.State_Uptime(self.func))
                
        # Override
        def exit(self):
            print "State_CPUTemp exit()"

            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_disconnect(player_slot, call_slot)
                pj.Lib.instance().player_destroy(self.player)


        def getCPUTemp(self):
            """
            CPU温度を取得して文字列で返す
            """
            try:
                s = subprocess.check_output(["/opt/vc/bin/vcgencmd","measure_temp"])
                val = str(s.split('=')[1][:-3])
            except:
                val = ""

            return val

    class State_MemState(StateBase):
        """
        「ただいまのメモリ状況は、トータルXXメガバイト中、XXメガバイトを使用、XXメガバイトの空きです。」と発話する。
        """
        def __init__(self, func):
            self.func = func
            self.player = -1
            
        # Override
        def enter(self):
            print "State_MemState enter()"
            
            # メモリ状況を取得
            mem = self.getMemState()

            # 発話内容を作成。
            if mem != "":
                msg = "ただいまのメモリ状況は、トータル%sメガバイト中、%sメガバイトを使用、%sメガバイトの空きです。" % mem
            else:
                msg = "メモリ状況の取得に失敗しました。"

            # 発話
            self.player = self.func.speak(msg)

        # Override
        def execute(self, dtmf=-1):
            print "State_MemState execute() %s" % dtmf

            if dtmf == "0":
                # イントロステートに変更
                self.func.changeState(self.func.State_Help(self.func))
            elif dtmf == "1":
                # CPU温度ステートに変更
                self.func.changeState(self.func.State_CPUTemp(self.func))
            elif dtmf == "2":
                # メモリ状況ステートに変更
                self.func.changeState(self.func.State_MemState(self.func))
            elif dtmf == "3":
                # 起動時間ステートに変更
                self.func.changeState(self.func.State_Uptime(self.func))
                
        # Override
        def exit(self):
            print "State_MemState exit()"

            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_disconnect(player_slot, call_slot)
                pj.Lib.instance().player_destroy(self.player)


        def getMemState(self):
            """
            メモリの状況を取得。
            Return: タプル (total, used, free)
            """
            try:
                # メモリの状況を取得
                s = subprocess.check_output(["free", "-m"])
                
                # こんな感じのデータが返される
                #              total       used       free     shared    buffers     cached
                # Mem:           438        117        321          0         15         58
                # -/+ buffers/cache:         43        395
                # Swap:           99          0         99

                # 一行づつに分割
                tmp = s.split('\n')

                # " "で分割
                tmp = tmp[1].split()
                
                # 戻り値を作成
                val = (tmp[1], tmp[2], tmp[3])
            except:
                val = ""

            return val


    class State_Uptime(StateBase):
        """
        「起動してから、%s分経ちました。」と発話する。
        """
        def __init__(self, func):
            self.func = func
            self.player = -1
            
        # Override
        def enter(self):
            print "State_Uptime enter()"
            
            # 起動時間を取得
            time = self.getUptime()

            # 発話内容を作成。
            if time != "":
                msg = "起動してから、%s分経ちました。" % time
            else:
                msg = "起動時間の取得に失敗しました。"

            # 発話
            self.player = self.func.speak(msg)

        # Override
        def execute(self, dtmf=-1):
            print "State_Uptime execute() %s" % dtmf

            if dtmf == "0":
                # イントロステートに変更
                self.func.changeState(self.func.State_Help(self.func))
            elif dtmf == "1":
                # CPU温度ステートに変更
                self.func.changeState(self.func.State_CPUTemp(self.func))
            elif dtmf == "2":
                # メモリ状況ステートに変更
                self.func.changeState(self.func.State_MemState(self.func))
            elif dtmf == "3":
                # 起動時間ステートに変更
                self.func.changeState(self.func.State_Uptime(self.func))
                
        # Override
        def exit(self):
            print "State_Uptime exit()"

            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player != -1:
                player_slot = pj.Lib.instance().player_get_slot(self.player)
                call_slot = current_call.info().conf_slot
                pj.Lib.instance().conf_disconnect(player_slot, call_slot)
                pj.Lib.instance().player_destroy(self.player)


        def getUptime(self):
            """
            UPTIMEの情報を取得して、起動時間を返す。
            """
            try:
                # uptimeの情報を取得
                s = subprocess.check_output(["uptime"])

                # 取得した値はこのようになっている。
                # 09:04:21 up 58 min,  1 user,  load average: 0.02, 0.03, 0.05
                # 09:09:29 up  1:03,  1 user,  load average: 0.01, 0.02, 0.05
                
                # "up"から","のあいだで切り出し。
                val = s[s.index("up")+len("up"):s.index(",")]

                # 1時間以上で表記が変わる。
                if val.find("min") != -1:
                    val = val[0:val.index(" min")]
                else:
                    val = val.replace(":", "時間")

                # 不要なスペースが含まれている場合は削除
                val = val.replace(" ", "")

            except ValueError, e:
                val = ""

            return val



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




