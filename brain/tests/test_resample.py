from jarvis_brain.voice.resample import resample_pcm_s16le


def test_identity_when_rates_match() -> None:
    data = b"\x00\x01\x00\x02"
    assert resample_pcm_s16le(data, 16000, 16000) == data


def test_24k_to_16k_shortens() -> None:
    # 24 samples at 24 kHz = 1 ms → ~16 samples at 16 kHz
    samples = b"\x00\x10" * 24
    out = resample_pcm_s16le(samples, 24000, 16000)
    assert len(out) == 16 * 2
