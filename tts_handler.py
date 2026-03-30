import os
from pathlib import Path
from openai import OpenAI

class TTSHandler:
    """Hanterar Text-to-Speech med OpenAI TTS API"""

    def __init__(self, api_key: str):
        """
        Initiera TTS handler

        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        self.output_dir = Path("/tmp/gideon_audio")
        self.output_dir.mkdir(exist_ok=True)

    def generate_speech(self, text: str, voice: str = "nova") -> Path:
        """
        Generera tal från text

        Args:
            text: Text att konvertera till tal
            voice: OpenAI voice (alloy, echo, fable, onyx, nova, shimmer)

        Returns:
            Path till genererad audio-fil
        """
        try:
            # Generera unikt filnamn
            import time
            timestamp = int(time.time() * 1000)
            output_file = self.output_dir / f"response_{timestamp}.mp3"

            # Anropa OpenAI TTS
            response = self.client.audio.speech.create(
                model="tts-1",  # eller "tts-1-hd" för högre kvalitet
                voice=voice,
                input=text
            )

            # Spara till fil
            response.stream_to_file(str(output_file))

            return output_file

        except Exception as e:
            raise Exception(f"Kunde inte generera tal: {str(e)}")

    def cleanup_old_files(self, max_age_seconds: int = 3600):
        """
        Rensa gamla audio-filer

        Args:
            max_age_seconds: Max ålder i sekunder (default 1 timme)
        """
        import time
        now = time.time()

        for file in self.output_dir.glob("response_*.mp3"):
            if now - file.stat().st_mtime > max_age_seconds:
                file.unlink()
