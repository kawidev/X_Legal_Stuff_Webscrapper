from pathlib import Path

from x_legal_stuff_webscrapper.media_downloader import _store_blob_dedup


def test_store_blob_dedup_reuses_same_hash_file(tmp_path: Path) -> None:
    blob = b"fake-image-bytes"
    path1, sha1 = _store_blob_dedup(tmp_path, blob, "https://example.com/a.jpg", "image/jpeg")
    path2, sha2 = _store_blob_dedup(tmp_path, blob, "https://example.com/b.jpg", "image/jpeg")

    assert sha1 == sha2
    assert path1 == path2
    assert path1.exists()
