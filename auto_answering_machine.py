#! /usr/bin/env python                                                                   
# -*- coding: utf-8 -*-

"""
auto_answering_machine.py

Copyright (C) 2014 Shun ITO <movingentity@gmail.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import abc
import argparse
import math
import pjsua as pj
import subprocess
import time
import wave


class PhoneCallback(pj.AccountCallback, pj.CallCallback):
    """
    電話機能のコールバッククラス。
    受話、DTMF受付等をする。
    DTMFを受け付けると、Functionクラスのupdate()を実行する。
    """
    def __init__(self, func, account=None, call=None):
        pj.AccountCallback.__init__(self, account)
        pj.CallCallback.__init__(self, call)

        # FunctionBaseクラスを継承していないクラスの場合はエラー
        assert isinstance(func, FunctionBase)

        self.func = func
 
    def on_incoming_call(self, call):
        """
        Override(pj.AccountCallback)
        Notification on incoming call
        """
        global current_call 

        # 電話中
        if current_call:
            call.answer(486, "Busy")
            return
            
        print "Incoming call from ", call.info().remote_uri

        current_call = call
        current_call.set_callback(self)

        # 受話する
        current_call.answer(180)        
        current_call.answer(200)


    def on_dtmf_digit(self, digits):
        """
        Override(pj.CallCallback)
        Notification on incoming DTMF digits.
        """
        print "INCOMING DTMF:%s" % digits

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

        print "Call with", self.call.info().remote_uri,
        print "is", self.call.info().state_text,
        print "last code =", self.call.info().last_code, 
        print "(" + self.call.info().last_reason + ")"
        
        # 切断
        if self.call.info().state == pj.CallState.DISCONNECTED:
            current_call = None
            print 'Current call is', current_call

    def on_media_state(self):
        """
        Override(pj.CallCallback)
        Notification when call's media state has changed.
        """
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            # Connect the call to sound device
            call_slot = self.call.info().conf_slot
            print "Media is now active"
            
            # イントロステートをセットして自動応答スタート
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

    """
    自動応答マシンの機能クラス。(FunctionBaseクラスを継承)
    DTMF入力に応じて、CPU温度、メモリ状況、起動時間を発話する。
    """

    def __init__(self, aq_path, tmp_dir, tmpfile_name):
        # パラメータを保存
        self.AQUESTALKPI_PATH = aq_path
        self.TMPFILE_PATH = tmp_dir + tmpfile_name

        # 初期ステートを設定。
        self.currentState = self.State_Intro(self)

    # Override
    def update(self, dtmf=-1):
        # StateBaseクラスを継承していない場合はエラー
        assert isinstance(self.currentState, StateBase)
        # 実行
        self.currentState.execute(dtmf)

    def changeState(self, state):
        # StateBaseクラスを継承していない場合はエラー
        assert isinstance(state, StateBase)

        # 現在のステートクラスのexit()を実行
        self.currentState.exit()

        # 新しいステートクラスを、現在のステートクラスとして設定
        self.currentState = state

        # 現在のステートクラス（新ステートクラス）のenter()を実行
        self.currentState.enter()


    def createWavfile(self, text):
        """
        渡されたテキストをAquesTalk Piを使ってwavファイルに変換、
        指定されたTMPディレクトリに、指定された名前で保存する。
        Return: 音声の長さ(秒)
        """
        try:
            # 声種f1
            subprocess.check_call([self.AQUESTALKPI_PATH, text, "-o", self.TMPFILE_PATH])
            # 声種f2
            #subprocess.check_call([self.AQUESTALKPI_PATH, "-v", "f2", text, "-o", self.TMPFILE_PATH])
        except subprocess.CalledProcessError, (p):
            print 'subprocess.CalledProcessError: cmd:%s returncode:%s' % (p.cmd, p.returncode)
            return 0

        # できたWavファイルを解析。
        try:
            wr = wave.open(self.TMPFILE_PATH, "r")
        except wave.Error, e:
            print "Error open wavfile", e
            return 0

#        print "長さ（秒）:", math.ceil(float(wr.getnframes()) / wr.getframerate())
        
        # 小数点切り上げしたファイルの長さ(秒)を返す
        return math.ceil(float(wr.getnframes()) / wr.getframerate())


    def speak(self, text):
        """
        渡されたテキストをwavファイルに変換して、
        できたwavファイルを再生する。
        wavファイルは読み込み後、削除する。
        Return: Player番号
        """
        global current_call

        # テキストが空の場合はリターン
        if text == None:
            return -1

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
            msg = "こんにちは。こちらはラズベリーパイです。CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は、0を入力してください。"
            self.player = self.func.speak(msg)

        def execute(self, dtmf=-1):
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
            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player == -1:
                return
            
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
            msg = "CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は、0を入力してください。"
            self.player = self.func.speak(msg)

        def execute(self, dtmf=-1):
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
            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player == -1:
                return

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
            if dtmf == "0":
                # ヘルプステートに変更
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
            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player == -1:
                return

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
            if dtmf == "0":
                # ヘルプステートに変更
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
            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player == -1:
                return

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

            if dtmf == "0":
                # ヘルプステートに変更
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
            # 音声の再生に使ったプレイヤーの後処理をする
            if self.player == -1:
                return

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
                
                # 1時間を超えるとこのようになる。
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

    # 引数解析
    parser = argparse.ArgumentParser(description=u"SIPによる接続に自動応答し、DTMF入力値に応じて、CPU温度、メモリ状況、起動時間を発話する。",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('-a', '--aquestalkpi',
                        dest="aquestalk_pi_path",
                        help="Path to AquesTalkPi")
    
    parser.add_argument("-d", "--dir",
                        dest="tmp_dir",
                        default="/tmp/",
                        help="Path of directory to save temporary wav file")

    parser.add_argument("-l", "--loglevel",
                        dest="log_level",
                        default=3,
                        help="Level of input verbosity")

    parser.add_argument("-n", "--name",
                        dest="tmpfile_name",
                        default="aqout.wav",
                        help="Name of temporary wav file")

    parser.add_argument("-p", "--port",
                        dest="in_port_num",
                        type=int,
                        help="Incoming port number")

    args = parser.parse_args()


    # 必須項目が引数で指定されていない場合は、問い合わせする。
    if args.aquestalk_pi_path is None:
        args.aquestalk_pi_path = raw_input("Path to AquesTalkPi: ")

    if args.in_port_num is None:
        args.in_port_num = int(raw_input("Incoming port number: "))

    #
    try:
        current_call = None

        lib = pj.Lib()
        lib.init(log_cfg = pj.LogConfig(level=args.log_level, callback=log_cb))

        transport = lib.create_transport(pj.TransportType.UDP, pj.TransportConfig(args.in_port_num))
        print "\nListening on", transport.info().host, 
        print "port", transport.info().port

        #
        lib.set_null_snd_dev()

        # Start the library
        lib.start()

        # Init Function
        myfunc = Func_AnsweringMachine(aq_path=args.aquestalk_pi_path,
                                       tmp_dir=args.tmp_dir,
                                       tmpfile_name=args.tmpfile_name)

        # Create local account
        acc = lib.create_account_for_transport(transport, cb=PhoneCallback(myfunc))

        # loop
        while(True):
            var = raw_input("Please type 'q' to quit\n")
            if var == "q":
                break
            
        # cleaning
        transport = None
        acc.delete()
        acc = None
        lib.destroy()
        lib = None

    except pj.Error, e:
        print "Exception: %s" % e
        lib.destory()
        lib = None
