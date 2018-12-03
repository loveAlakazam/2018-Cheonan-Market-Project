#source from: https://cloud.google.com/text-to-speech/docs/quickstart-client-libraries
import os
import sys
import time
from google.cloud import texttospeech
class TextToSpeech:
    def __init__(self,answer):
        self.text= answer
    
    def tts_play(self,fname='answer'):
        client = texttospeech.TextToSpeechClient()
    
        synthesize_input = texttospeech.types.SynthesisInput(text=self.text)

        voice= texttospeech.types.VoiceSelectionParams(
            language_code='ko-KR',
            ssml_gender= texttospeech.enums.SsmlVoiceGender.FEMALE)
    
        audio_config = texttospeech.types.AudioConfig(
            audio_encoding = texttospeech.enums.AudioEncoding.MP3)

        response = client.synthesize_speech(synthesize_input, voice, audio_config)
        filename=str(fname)+'.mp3'
        with open(filename, 'wb')as out:
            out.write(response.audio_content)
            print("Audio content written to file answer.mp3")

        os.system('mpg123 '+filename)
