from pathlib import Path

from jarvis_brain.voice.wav import pcm_rms, wav_info, write_wav


def test_write_and_measure(tmp_path: Path) -> None:
    # 16000 samples of a 440-ish square-ish tone at 16 kHz, 16-bit
    pcm = (b"\x00\x40" * 80) + (b"\x00\xc0" * 80)
    dest = write_wav(tmp_path / "t.wav", pcm, 16000)
    info = wav_info(dest)
    assert info["sample_rate"] == 16000
    assert info["frames"] == 160
    assert info["duration_s"] == 0.01
    assert pcm_rms(pcm) > 50
