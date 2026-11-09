import pytest

from barometre import collect

CSV = "observation_date,VIXCLS\n2026-10-28,18.5\n2026-10-29,.\n2026-10-30,19.1\n2026-11-02,\n"


def test_parse_ignores_missing_values():
    s = collect.parse_fred_csv(CSV)
    assert list(s.values) == [18.5, 19.1] and s.index[-1].date().isoformat() == "2026-10-30"


def test_parse_accepts_old_header_name():
    assert len(collect.parse_fred_csv("DATE,X\n2026-01-01,1\n2026-02-01,2\n")) == 2


@pytest.mark.parametrize("bad", ["<html><body>Erreur 403</body></html>", "", "pas,de\n,\n", "DATE,X\n"])
def test_parse_rejects_bad_responses(bad):
    with pytest.raises(ValueError):
        collect.parse_fred_csv(bad)


def test_fetch_ok_writes_cache(tmp_path):
    s, st = collect.fetch_series("VIXCLS", fetch=lambda u: CSV, cache_dir=tmp_path)
    assert st.startswith("ok") and (tmp_path / "VIXCLS.csv").read_text() == CSV and len(s) == 2


def test_fetch_falls_back_to_cache_and_says_so(tmp_path):
    (tmp_path / "VIXCLS.csv").write_text(CSV)

    def boom(u):
        raise OSError("réseau coupé")
    s, st = collect.fetch_series("VIXCLS", fetch=boom, cache_dir=tmp_path)
    assert st.startswith("cache") and "réseau coupé" in st and len(s) == 2


def test_fetch_html_error_page_is_not_cached(tmp_path):
    s, st = collect.fetch_series("VIXCLS", fetch=lambda u: "<html>blocked</html>", cache_dir=tmp_path)
    assert s is None and st.startswith("indisponible") and not (tmp_path / "VIXCLS.csv").exists()


def test_offline_uses_cache_only(tmp_path):
    (tmp_path / "VIXCLS.csv").write_text(CSV)
    called = []
    s, st = collect.fetch_series("VIXCLS", fetch=lambda u: called.append(u), cache_dir=tmp_path, offline=True)
    assert not called and st.startswith("cache") and len(s) == 2


def test_collect_all_reports_each_series(tmp_path):
    inds = [{"series": "A"}, {"series": "B"}, {"series": "A"}]
    raw, status = collect.collect_all(inds, fetch=lambda u: CSV if "id=A" in u else "<html>x</html>", cache_dir=tmp_path)
    assert list(raw) == ["A"] and status["A"].startswith("ok") and status["B"].startswith("indisponible")


def test_read_local_files_counts_as_fresh(tmp_path):
    (tmp_path / "VIXCLS.csv").write_text(CSV, encoding="utf-8")
    s, st = collect.read_local("VIXCLS", tmp_path)
    assert st.startswith("ok") and len(s) == 2
    s2, st2 = collect.read_local("ABSENT", tmp_path)
    assert s2 is None and st2.startswith("indisponible")


API_JSON = '{"observations":[{"date":"2026-10-01","value":"19.5"},{"date":"2026-10-02","value":"."},{"date":"2026-10-03","value":"20.1"}]}'


def test_api_json_is_converted_and_cached(tmp_path):
    seen = []
    def fake(url):
        seen.append(url)
        return API_JSON
    s, st = collect.fetch_series("VIXCLS", fake, tmp_path, key="SECRETKEY123")
    assert "api.stlouisfed.org" in seen[0] and "file_type=json" in seen[0]
    assert st.startswith("ok") and "API FRED" in st
    assert list(s.values) == [19.5, 20.1]                       # « . » ignoré
    assert (tmp_path / "VIXCLS.csv").read_text().startswith("observation_date,VIXCLS")


def test_api_error_never_leaks_the_key(tmp_path):
    def boom(url):
        raise OSError("échec pour " + url)
    s, st = collect.fetch_series("VIXCLS", boom, tmp_path, key="SECRETKEY123")
    assert s is None and "SECRETKEY123" not in st and "***" in st
    def bad(url):
        return '{"error_code":400,"error_message":"Bad Request.  The value for variable api_key is not registered."}'
    s, st = collect.fetch_series("VIXCLS", bad, tmp_path, key="SECRETKEY123")
    assert s is None and "not registered" in st and "SECRETKEY123" not in st


def test_api_key_from_env(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "  abc  ")
    assert collect.api_key() == "abc"
