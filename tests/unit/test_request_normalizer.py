"""Unit tests for RequestNormalizer."""
from app.core.enums import ChannelType
from app.core.normalizer import RequestNormalizer


def test_wake_prefix_removal():
    normalizer = RequestNormalizer()
    cases = [
        ("Hey Jarvis, check my GitHub CI builds", "check my GitHub CI builds"),
        ("Hi Jarvis, remind me tomorrow at 9", "remind me tomorrow at 9"),
        ("Maapla, check battery status", "check battery status"),
        ("Please find failed builds", "find failed builds"),
        ("Can you upload this to Drive", "upload this to Drive"),
    ]
    for raw, expected in cases:
        payload = normalizer.normalize(raw, channel=ChannelType.VOICE)
        assert payload.cleaned_text == expected
        assert payload.original_raw == raw


def test_filler_word_removal():
    normalizer = RequestNormalizer()
    raw = "uh remind me um to study er Java ah tomorrow"
    payload = normalizer.normalize(raw)
    assert payload.cleaned_text == "remind me to study Java tomorrow"


def test_language_detection():
    normalizer = RequestNormalizer()
    assert normalizer.normalize("Check CI builds").detected_language == "en"
    assert normalizer.normalize("Maapla innaiku battery status sollu").detected_language == "en-ta"
    assert normalizer.normalize("நாளை காலை 9 மணிக்கு நினைவூட்டு").detected_language == "ta"


def test_empty_input_handling():
    normalizer = RequestNormalizer()
    payload = normalizer.normalize("   ")
    assert payload.cleaned_text == ""
    assert payload.detected_language == "en"
