# PJSIPとAquesTalk Piを使って自動応答の音声ガイダンスを作る

Raspberry PiにIP電話をかけると、音声ガイダンスで端末の状態を教えてくれると面白いなと思い、作ってみることにしました。

動作を収録した動画を撮りました。

https://user-images.githubusercontent.com/3046839/210189023-49534277-d50f-4e8f-829e-1a93996d0490.mp4

## 概要
SIP(Session Initiation Protocol)による着信に自動応答し、ガイダンスを発話、DTMF(Dual-Tone Multi-Frequency)入力を待ち受けます。DTMF入力があった場合、入力された値に応じて、CPU温度、メモリ容量、起動時間、ヘルプを発話します。相手が電話を切ると、待機状態に戻ります。プログラミング言語にはPython(2.7)を使っています。

## 必要なもの
-   PJSIP(PJSUA)  
    C言語で書かれたオープンソースのマルチメディアコミュニケーションライブラリ。

-   AquesTalk Pi  
    [株式会社アクエスト](http://www.a-quest.com/)から公開されている音声合成プログラム。個人が非営利の目的に使う場合は無償で使える(感謝!!)。

## 使い方
1.  PJSIP及びPJSUAをインストールします。（[こちら](https://gist.github.com/ll0s0ll/ec791b30d03f75e666014ead3097188c)にインストール方法を書いています）

1.  AquesTalk Piをダウンロード及び展開します。（ダウンロードは[こちら](http://www.a-quest.com/products/aquestalkpi.html)から。展開方法を説明したブログへのリンクも張られています。）展開先のパスが必要となりますので、控えておいてください。

1. ソースコード(auto\_answering\_machine.py)をダウンロードします。zipは[こちら](https://github.com/ll0s0ll/Py_Auto_Answering_Machine/archive/master.zip)。  
```$ git clone https://github.com/ll0s0ll/Py_Auto_Answering_Machine.git```

1. ディレクトリを移動して、実行します。auto\_answering\_machine.pyは、AquesTalk Piへのパスと、待ち受けのポート番号の指定が必要です。下記は、ホームディレクトリ下のaquestalkpiディレクトリにAquesTalk Piがあり、5060番ポートでSIPの接続を待ち受ける場合の例です。  
   ```
   $ cd Py_Auto_Answering_Machine/
   $ python auto_answering_machine.py -a ~/aquestalkpi/AquesTalkPi -p 5060
   ```
1. プログラムが起動すると、PJSIPのログとともに下記が出力されると、SIPの接続を待機している状態になります。表示されるIPアドレスは、Raspberry PiのIPアドレスです。終了させる場合は「q」をタイプしてください。  
   ```
   Listening on 192.168.10.15 port 5060
   Please type 'q' to quit
   ```

1. SIPに対応したソフトからRaspberry Piに電話をかけると、受話し、「*こんにちは。こちらはラズベリーパイです。CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は、0を入力してください*」と発話します。IPアドレスが192.168.10.3の’MacBook’と名付けた端末から電話をかけた場合は、以下のように出力されます。
   ```
   Incoming call from &quot;MacBook&quot; &lt;sip:MacBook@192.168.10.3&gt;
   Call with "MacBook" <sip:MacBook@192.168.10.3> is EARLY last code = 180 (Ringing)
   Media is now active
   Call with "MacBook" <sip:MacBook@192.168.10.3> is CONNECTING last code = 200 (OK)
   Call with "MacBook" <sip:MacBook@192.168.10.3> is CONFIRMED last code = 200 (OK)
   ```

1. さらにDTMF入力をすると、入力された値により、Raspberry Piの端末の状況を、以下のように発話します。

   - 0が入力された場合  
   「*CPU温度を知りたい場合は、1を。メモリ状況を知りたい場合は、2を。起動時間を知りたい場合は、3を入力してください。途中で使い方を確認したくなった場合は、0を入力してください*」
   
   - 1が入力された場合  
   「*ただいまのCPU温度はxx度です。*」
   
   - 2が入力された場合  
   「*ただいまのメモリ状況は、トータルxxメガバイト中、xxメガバイトを使用、xxメガバイトの空きです。*」
   
   - 3が入力された場合  
   「*起動してから、xx分経ちました*」

1. 電話を切ると、以下のように出力されて、待機状態に戻ります。終了する場合は「q」をタイプしてください。  
   `Current call is None`

1. -h オプションをつけて起動すると、簡単なヘルプを表示します。  
   `$ python auto_answering_machine.py -h`
