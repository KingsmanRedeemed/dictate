# Lessons

## Whisper tail-hallucinations in push-to-talk

**Root cause**
- Whisper can decode trailing silence/ambient noise into plausible text, especially at the end of a
  recording.
- With `condition_on_previous_text=True`, the decoder conditions on its own prior output across
  segments and can "continue" into fabricated endings (hallucination chaining).
- Generous VAD padding (`speech_pad_ms`) and long silence windows (`min_silence_duration_ms`) feed
  more non-speech tail audio into the model, increasing the chance of hallucinations.

**Fix**
- In `src/dictate/stt/faster_whisper_backend.py`, pass:
  - `condition_on_previous_text=False` (prevents chaining on prior model output)
  - `no_speech_threshold=0.6` (suppresses low-confidence no-speech segments)
  - Tightened VAD: `speech_pad_ms=50` and `min_silence_duration_ms=300`

