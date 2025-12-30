"""Translation services for multi-language job descriptions"""

import os
from typing import Optional

try:
    from googletrans import Translator
except ImportError:
    Translator = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class TranslationService:
    """Handles translation of job descriptions to English"""

    def __init__(self):
        self.google_translator = Translator() if Translator else None
        self.openai_client = None

        # Initialize OpenAI if API key is available
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and OpenAI:
            self.openai_client = OpenAI(api_key=openai_key)

    async def translate_to_english(self, text: str, source_lang: str = 'sv') -> Optional[str]:
        """
        Translate text to English

        Args:
            text: Text to translate
            source_lang: Source language code (default: 'sv' for Swedish)

        Returns:
            Translated text or None if translation fails
        """
        if not text or len(text.strip()) == 0:
            return text

        # Try OpenAI first (better quality)
        if self.openai_client:
            try:
                translated = await self._translate_with_openai(text, source_lang)
                if translated:
                    return translated
            except Exception:
                pass  # Fall back to Google Translate

        # Fall back to Google Translate
        if self.google_translator:
            try:
                translated = await self._translate_with_google(text, source_lang)
                if translated:
                    return translated
            except Exception:
                pass

        # If both fail, return original text
        return text

    async def _translate_with_openai(self, text: str, source_lang: str) -> Optional[str]:
        """Translate using OpenAI"""
        if not self.openai_client:
            return None

        try:
            prompt = f"Translate the following {source_lang.upper()} text to English. Maintain professional terminology and job-related vocabulary. Only return the translated text:\n\n{text}"

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
            )

            translated = response.choices[0].message.content.strip()
            return translated if translated else None

        except Exception:
            return None

    async def _translate_with_google(self, text: str, source_lang: str) -> Optional[str]:
        """Translate using Google Translate"""
        if not self.google_translator:
            return None

        try:
            # Google Translate expects language codes
            lang_map = {'sv': 'sv', 'zh': 'zh-CN'}
            source = lang_map.get(source_lang, 'auto')

            result = self.google_translator.translate(text, src=source, dest='en')
            return result.text if result and result.text else None

        except Exception:
            return None
