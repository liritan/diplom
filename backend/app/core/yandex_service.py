import requests
import struct
from typing import Optional
from langchain_community.chat_models import ChatYandexGPT
from app.core.config import settings

class YandexService:
    def __init__(self):
        self.folder_id = settings.YANDEX_FOLDER_ID
        self.api_key = settings.YANDEX_API_KEY
        self.llm = ChatYandexGPT(
            folder_id=self.folder_id,
            api_key=self.api_key,
            model_uri=f"gpt://{self.folder_id}/yandexgpt-lite",
            temperature=0.6,
        )

    async def get_chat_response(self, message: str) -> str:
        """
        Get response from YandexGPT via LangChain.
        """
        try:
            response = self.llm.invoke(message)
            return response.content
        except Exception as e:
            print(f"YandexGPT Error: {e}")
            return "Извините, я сейчас не могу ответить. Попробуйте позже."

    async def speech_to_text(self, audio_data: bytes) -> str:
        """
        Convert speech to text using Yandex SpeechKit.
        """
        url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
        }
        params = {"lang": "ru-RU", "folderId": self.folder_id}

        def _extract_wav_lpcm(data: bytes):
            if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                return None

            offset = 12
            fmt = None
            data_chunk = None

            while offset + 8 <= len(data):
                chunk_id = data[offset : offset + 4]
                chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
                chunk_start = offset + 8
                chunk_end = min(chunk_start + chunk_size, len(data))

                if chunk_id == b"fmt ":
                    if chunk_end - chunk_start >= 16:
                        audio_format, num_channels, sample_rate, _, _, bits_per_sample = struct.unpack_from(
                            "<HHIIHH", data, chunk_start
                        )
                        fmt = (audio_format, num_channels, sample_rate, bits_per_sample)
                elif chunk_id == b"data":
                    data_chunk = data[chunk_start:chunk_end]

                offset = chunk_start + chunk_size
                if offset % 2 == 1:
                    offset += 1

            if not fmt or data_chunk is None:
                return None

            audio_format, num_channels, sample_rate, bits_per_sample = fmt
            if audio_format != 1 or num_channels != 1 or bits_per_sample != 16:
                return None

            return data_chunk, int(sample_rate)
        
        try:
            wav = _extract_wav_lpcm(audio_data)
            if wav:
                pcm_data, sample_rate = wav
                params["format"] = "lpcm"
                params["sampleRateHertz"] = sample_rate
                body = pcm_data
            elif audio_data.startswith(b"OggS"):
                params["format"] = "oggopus"
                body = audio_data
            else:
                body = audio_data

            response = requests.post(url, headers=headers, params=params, data=body)
            if response.status_code != 200:
                print(f"STT Error: {response.text}")
                return ""
            
            result = response.json()
            return result.get("result", "")
        except Exception as e:
            print(f"SpeechKit STT Error: {e}")
            return ""

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        Convert text to speech using Yandex SpeechKit.
        """
        url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
        }
        data = {
            "text": text,
            "lang": "ru-RU",
            "voice": "filipp", # or 'alyss', 'jane', 'omazh', 'zahar', 'ermil'
            "folderId": self.folder_id,
            "format": "mp3"
        }
        
        try:
            response = requests.post(url, headers=headers, data=data)
            if response.status_code != 200:
                print(f"TTS Error: {response.text}")
                return None
            return response.content
        except Exception as e:
            print(f"SpeechKit TTS Error: {e}")
            return None

yandex_service = YandexService()
