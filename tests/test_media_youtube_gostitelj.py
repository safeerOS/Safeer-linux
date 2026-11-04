"""YouTube se prepozna po imenu gostitelja, ne po podnizu v netloc (pregled 4. 11. 2026)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import os_media  # noqa: E402


def _url(seznam):
    return seznam[0]["url"] if seznam else ""


def test_pravi_youtube_v_vdelavo():
    for url in ("https://www.youtube.com/watch?v=abc123", "https://youtube.com/watch?v=abc123",
                "https://m.youtube.com/watch?v=abc123", "https://youtu.be/abc123"):
        assert "youtube.com/embed/abc123" in _url(os_media._resolve_embed_or_direct_source(url, "v", "Vir")), url


def test_lazni_youtube_ni_vdelava():
    for url in ("https://youtube.com.zlobni.example/watch?v=abc123", "https://neyoutube.com/watch?v=abc123",
                "https://zlobni.example/youtube.com/watch?v=abc123",
                "https://youtube.com@zlobni.example/watch?v=abc123"):
        assert "youtube.com/embed" not in _url(os_media._resolve_embed_or_direct_source(url, "v", "Vir")), url
