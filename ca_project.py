# -*- encoding: utf8 -*-
from __future__ import division
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from six.moves import queue

import io
import os
import sys
import re
import time
import pyaudio
import google_tts #google_tts.py (text to speech)
import signal
import snowboydecoder #snowboydecoder
import webbrowser
#[END - import libraries ]
#Audio recording parameters
RATE=44100
CHUNK=int(RATE/10) #100ms

# global variable: interrupted
interrupted =  False

#command_list (skills)
cmdLists=[
        #command[0]     end_return_value[1]
        [u'끝내자', 0 ],
        [u'끝', 0],
        [u'제일 맛있는 집 알려 줘',1],
        [u'어디가 제일 맛있어', 1],
        [u'어디가 제일 맛있어어', 1],
        [u'웰빙 마늘떡볶이', 2],
        [u'웰빙 마늘떡볶이집 어디 있어',2],
        [u'웰빙 마늘떡볶이집 어디 있어어',2],
        [u'마늘떡볶이', 2],
        [u'마늘떡볶이 집 어디에 있어',2],
        [u'마늘떡볶이 집 어디에 있어어',2],
        [u'천리향 양꼬치', 3],
        [u'양꼬치',3],
        [u'천리향 양꼬치 집 어디 있어',3],
        [u'천리향 양꼬치 집 어디 있어어',3],
        [u'양꼬치 집 어디 있어',3],
        [u'양꼬치 집 어디 있어',3],
        [u'오복갈비',4],
        [u'오복갈비 집 어디에 있어',4],
        [u'오복갈비 집 어디에 있어어',4],
        [u'오복갈비 집 어디 있어',4],
        [u'오복갈비 집 어디 있어어',4],
        [u'지도 보여 줘', 5],
        [u'현재 위치 알려줘',5]
]

#command_list_answers
cmdAnswers=[
    [u'안녕히 가세요.'], #return value =0
    [u'천안 역전 시장에서 웰빙마늘 떡볶이랑 오복갈비, 처리향 양꼬치집이 가장 맛있고 유명해요.'],#return value=1
    [u'웰빙 마늘떡볶이집 위치를 알려드리겠습니다.'], #return value=2
    [u'처리향 양꼬치집 위치를 알려 드리겠습니다.'], #return value=3
    [u'오복갈비집 위치를 알려 드리겠습니다.'], #return value=4
    [u'현재위치를 알려 드리겠습니다.']] #return value=5

def signal_handler(signal, frame):
    global interrupted
    interrupted = True

def interrupt_callback():
    global interrupted
    return interrupted

def callkeyword():
    if len(sys.argv)==1:
        print("Usage:python3 cheoan_project.py "+"cheoan_market.pmdl")
        sys.exit(1)
    model = sys.argv[1] #모델
    
    #시그널 핸들러 이용.
    signal.signal(signal.SIGINT, signal_handler)
    detector = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
    print('Listening...Press Ctrl+C to exit')

    detector.start(detected_callback =snowboydecoder.play_audio_file,
                   interrupt_check = interrupt_callback,
                   sleep_time=0.03)

class MicrophoneStream(object):
    '''Opens a recording stream as a generator yielding the audio chunks'''
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        #Create a thread-safe buffer or audio data
        self._buff = queue.Queue()
        self.closed = True
        self.isPause= False

    def __enter__(self):
        self._audio_interface= pyaudio.PyAudio()
        self._audio_stream= self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            stream_callback = self._fill_buffer,)

        self.closed=False
        
        return self
    
    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed= True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk=self._buff.get()
            if chunk is None:
                return

            if self.isPause:
                continue
            
            data= [chunk]

            while True:
                try:
                    chunk= self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b''.join(data)

    def pause(self):
        self.isPause=True

    def restart(self):
        self.isPause=False
# end audio stream
        
# 스피치를 텍스트로 나타냄        
def speechToText():
    language_code='ko-KR'
    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding =enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code= language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests=(types.StreamingRecognizeRequest(audio_content=content)
                  for content in audio_generator)

        responses= client.streaming_recognize(streaming_config, requests)

        listen_print_loop(responses, stream)


# [Command Process fundtion : 명령처리함수..]
def command_process(stt):
    cmd =stt.strip()
    print('나: '+str(cmd))
    #명령리스트(cmdLists) 안의 명령과 비교하여 확인
    for cmdList in cmdLists:
        if str(cmd)==cmdList[0]: #cmdList안의 명령과 같다면..
            #answer_num이 가리키는 cmdList[1]은 integer 자료형을 갖는다.
            answer_num= int(cmdList[1])
            #그러나 cmdAnsers[anser_num]이 가리키는 건 문자열이 아니라 리스트
            #리스트를 문자열로 나타낸다.
            ans0= ''.join(cmdAnswers[answer_num])
            print('천안 역전: '+ ans0)
            ans=google_tts.TextToSpeech(ans0) #대답을 tts로 재생.
            ans.tts_play()
            return cmdList[1]

    #명령이 없거나, 알아 듣지 못할 때(return value=-1)
    sorry=google_tts.TextToSpeech("죄송합니다. 알아듣지 못했습니다.")
    sorry.tts_play(fname='sorry')
    print('천안 역전: '+ "죄송합니다. 알아듣지 못했습니다.")
    return -1

def listen_print_loop(responses, mic):
    num_chars_printed= 0
    for response in responses:
        if not response.results:
            continue

        result= response.results[0]
        if not result.alternatives:
            continue
        transcript = result.alternatives[0].transcript
        overwrite_chars= ' '*(num_chars_printed - len(transcript))
        
        if not result.is_final:
            sys.stdout.write('나 : ')
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()
            num_chars_printed = len(transcript)

        else:
            mic.pause() #pause => isPause=True
            cmd_return_number= command_process(stt=transcript)
            if cmd_return_number==0: #command_process값이 0이면 종료
                break
            elif cmd_return_number >=2:
                mic.pause()
                #지도 API를 이용하여 답변을 해주는 부분이다.
                if cmd_return_number ==2:
                    #현재위치와 웰빙 마늘떡볶이 지도상 위치정보를 갖는다.
                    url='file:///home/pi/cheoan_project/position2.html'
                    webbrowser.open(url)
                    
                elif cmd_return_number ==3:
                    #현재위치와 천리향 양꼬치집 지도상 위치정보를 갖는다.
                    url='file:///home/pi/cheoan_project/position3.html'
                    webbrowser.open(url,'utf-8')
                    
                elif cmd_return_number ==4:
                    #현재위치와 오복갈비집 지도상 위치정보를 갖는다.
                    url='file:///home/pi/cheoan_project/position4.html'
                    webbrowser.open(url,'utf-8')
                else: #cmd_return_number==5
                    #현재위치를 지도상 위치정보를 갖는다.
                    url='file:///home/pi/cheoan_project/position5.html'
                    webbrowser.open(url,'utf-8')
                
            mic.restart() #restart=> isPause=False
           

def main():
    while(1):
        #키워드 '헤이 천안역전' 을 부른다.
        callkeyword()

        # 띵 소리로 키워드를 인지 후 '무엇을 도와드릴까요?'라고 물어본다.
        #os.system('mpg123 hello.mp3')
        hello=google_tts.TextToSpeech('안녕하세요. 무엇을 도와드릴까요?')
        hello.tts_play(fname='hello')
    
        # 사용자가 말한 명령을 text로 변환시킨다.
        speechToText()
    
        # 사용자가 말한 명령이 skills 리스트에 해당하는지 확인
        # 없다면 '죄송합니다. 잘 못알아 들었습니다.'라고 대답.
        # 있다면 해당 답변을..

        # 가게의 위치가 어디냐는 질문을 할 경우.. 자바스크립트를 이용한..
        # 네이버지도 API를 이용한다

        # after stt/tts services, restart keyword detection
        #callkeyword()

if __name__=='__main__':
    main()

