import gradio as gr
import speech_recognition as sr
from gtts import gTTS
from io import BytesIO
from pydub import AudioSegment
from pydub.playback import play
from openai import OpenAI
from elevenlabs import generate, play as elevenlabs_play, set_api_key
from pathlib import Path
import threading
from dotenv import load_dotenv
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

# OpenAI and ElevenLabs clients initialization
client = OpenAI(api_key=openai_api_key)
set_api_key(elevenlabs_api_key)

recognition_methods = ["Google", "OpenAI", "None"]
audio_output_methods = ["Google", "OpenAI", "ElevenLabs", "None"]
supported_languages = ["English", "Arabic", "Chinese", "Czech", "Dutch", "French", "German", "Greek", "Hindi",
                       "Italian", "Japanese", "Korean", "Polish", "Portuguese", "Russian", "Slovak",
                       "Spanish", "Turkish"]


class SpeechProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def record_audio(self):
        with sr.Microphone() as source:
            print("Listening...")
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
            print("Recorded...")
            return audio

    def convert_audio_to_text(self, method, audio_data):
        try:
            if method == "Google":
                return self.recognize_with_google(audio_data)
            elif method == "OpenAI":
                return self.recognize_with_openai(audio_data)
            elif method == "None":
                return ""
        except sr.RequestError:
            return "API request failed. Please check your internet connection."
        except sr.UnknownValueError:
            return "No speech was detected. Please try again."
        except Exception as e:
            return f"An error occurred: {str(e)}"

    def recognize_with_google(self, audio_data):
        try:
            return self.recognizer.recognize_google(audio_data, language="en-in").lower()
        except Exception as e:
            return f"Error: {str(e)}"

    def recognize_with_openai(self, audio_data):
        audio_file_path = "./recorded_audio.wav"
        with open(audio_file_path, "wb") as af:
            af.write(audio_data.get_wav_data(convert_rate=16000, convert_width=2))
        with open(audio_file_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            return result.text.lower()

    def convert_text_to_speech(self, text, method):
        if method == "Google":
            self.speak_with_google(text)
        elif method == "OpenAI":
            self.speak_with_openai(text)
        elif method == "ElevenLabs":
            self.speak_with_elevenlabs(text)
        elif method == "None":
            pass

    def speak_with_google(self, text):
        tts = gTTS(text=text, lang='en', slow=False)
        fp = BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio = AudioSegment.from_file(fp, format="mp3")
        silence = AudioSegment.silent(duration=400)
        audio_with_silence = silence + audio
        play(audio_with_silence)

    def speak_with_openai(self, text):
        speech_file_path = Path("./speech.mp3")
        response = client.audio.speech.create(model="tts-1", voice="nova", input=text)
        response.stream_to_file(speech_file_path)
        sound = AudioSegment.from_file(speech_file_path, format="mp3")
        silence = AudioSegment.silent(duration=400)
        audio_with_silence = silence + sound
        play(audio_with_silence)

    def speak_with_elevenlabs(self, text):
        try:
            voice = "Dorothy"
            model = "eleven_multilingual_v2"
            speech = generate(text=text, voice=voice, model=model)
            # elevenlabs_play(speech)
            fp = BytesIO()
            fp.write(speech)
            fp.seek(0)
            audio = AudioSegment.from_file(fp, format="mp3")
            silence = AudioSegment.silent(duration=400)
            audio_with_silence = silence + audio
            play(audio_with_silence)

        except Exception as e:
            print(f"Error in ElevenLabs speech synthesis: {e}")
            return f"Error: {e}"


class Translator:
    def __init__(self, client):
        self.client = client

    def translate_text(self, source_text, target_language):
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                 "content": f"Translate the following sentence into {target_language}: {source_text}."},
                {"role": "user", "content": source_text}
            ]
        )
        return completion.choices[0].message.content


def main():
    speech_processor = SpeechProcessor()
    translator = Translator(client)

    def record_and_recognize(recognition_method):
        audio = speech_processor.record_audio()
        return speech_processor.convert_audio_to_text(recognition_method, audio)

    def translate_and_speak(text, target_language, output_method, input_language="English"):
        # if input_language.lower() == target_language.lower():
        #    translated_text = text
        # else:
        translated_text = translator.translate_text(text, target_language)

        # Start a new thread for text-to-speech to not block the UI
        tts_thread = threading.Thread(target=speech_processor.convert_text_to_speech,
                                      args=(translated_text, output_method))
        tts_thread.start()
        return translated_text

    def clear_interface():
        return "", ""

    # Gradio Interface
    with gr.Blocks() as app:
        gr.Markdown("<center><h1>GPT Universal Translator</h1></center>")
        with gr.Row():
            with gr.Column(scale=4):
                with gr.Row():
                    record_button = gr.Button("Record Audio")
                    translate_button = gr.Button("Translate")
                with gr.Row():
                    transcribed_textbox = gr.Textbox(label="Input Text", interactive=True, lines=5)
                with gr.Row():
                    translated_textbox = gr.Textbox(label="Output Text", interactive=True, lines=5)

            with gr.Column(scale=1):
                recognition_method_dropdown = gr.Dropdown(choices=recognition_methods, label="Voice Recognition Engine",
                                                          value="Google")
                language_dropdown = gr.Dropdown(
                    choices=supported_languages,
                    label="Output Language", value="English")
                output_method_dropdown = gr.Dropdown(choices=audio_output_methods,
                                                     label="Output Audio Engine",
                                                     value="Google")

                clear_button = gr.Button("Clear")
                dark_mode_btn = gr.Button("Dark Mode")

        record_button.click(fn=record_and_recognize, inputs=[recognition_method_dropdown], outputs=transcribed_textbox)
        translate_button.click(fn=translate_and_speak,
                               inputs=[transcribed_textbox, language_dropdown, output_method_dropdown],
                               outputs=translated_textbox)
        clear_button.click(fn=clear_interface, inputs=[], outputs=[transcribed_textbox, translated_textbox])

        dark_mode_btn.click(
            None,
            None,
            None,
            _js="""() => {
                    if (document.querySelectorAll('.dark').length) {
                        document.querySelectorAll('.dark').forEach(el => el.classList.remove('dark'));
                    } else {
                        document.querySelector('body').classList.add('dark');
                    }
                }""",
        )

    app.launch()


if __name__ == "__main__":
    main()
