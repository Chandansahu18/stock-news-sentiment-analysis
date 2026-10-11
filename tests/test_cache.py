import json
import time

from app.cache import JsonFileCache, get_cache


def test_save_and_read_roundtrip(tmp_path):
    cache = JsonFileCache(tmp_path)
    cache.save("news_TCS", {"a": 1})
    assert cache.get_fresh("news_TCS", max_age_seconds=60) == {"a": 1}


def test_expired_entry_is_not_fresh_but_still_readable(tmp_path):
    cache = JsonFileCache(tmp_path)
    cache.save("k", [1, 2])
    file = next(tmp_path.glob("k.json"))
    record = json.loads(file.read_text())
    record["saved_at"] = time.time() - 1000
    file.write_text(json.dumps(record))
    assert cache.get_fresh("k", max_age_seconds=60) is None
    assert cache.get_even_if_expired("k") == [1, 2]


def test_missing_and_corrupt_files_are_handled(tmp_path):
    cache = JsonFileCache(tmp_path)
    assert cache.get_fresh("nope", 60) is None
    (tmp_path / "bad.json").write_text("{not json")
    assert cache.get_fresh("bad", 60) is None
    assert cache.get_even_if_expired("bad") is None


def test_key_cannot_escape_the_cache_folder(tmp_path):
    folder = tmp_path / "cache"
    JsonFileCache(folder).save("../../evil", {"x": 1})
    assert not (tmp_path / "evil.json").exists()
    files = list(folder.glob("*.json"))
    assert len(files) == 1 and files[0].parent == folder


def test_no_temp_files_left_behind(tmp_path):
    JsonFileCache(tmp_path).save("k", {"a": 1})
    assert not list(tmp_path.glob("*.tmp"))


def test_get_cache_follows_the_cache_dir_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "elsewhere"))
    get_cache().save("k", 1)
    assert (tmp_path / "elsewhere" / "k.json").exists()
