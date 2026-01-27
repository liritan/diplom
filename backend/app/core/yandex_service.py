import requests
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
        params = {
            "lang": "ru-RU",
            "folderId": self.folder_id,
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, data=audio_data)
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
