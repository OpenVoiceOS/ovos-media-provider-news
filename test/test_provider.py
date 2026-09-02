"""Unit tests for NewsMediaProvider (bundled catalog, no network)."""
from unittest.mock import patch

from mediavocab import MediaType, Release, Signals, StreamMode

from ovos_media_provider_news import NewsMediaProvider

_FAKE_DB = {
    "en-US": {
        "NPR": {
            "aliases": ["NPR", "NPR News", "National Public Radio"],
            "uri": "news//https://www.npr.org/podcasts/500005/npr-news-now",
            "image": "./res/images/NPR.png",
            "secondary_langs": ["en"],
        },
        "FOX": {
            "aliases": ["FOX", "FOX News"],
            "uri": "rss//http://feeds.foxnewsradio.com/FoxNewsRadio",
            "secondary_langs": ["en"],
        },
    },
    "pt-PT": {
        "RTP": {
            "aliases": ["RTP", "Antena 1"],
            "uri": "rss//http://www.rtp.pt/play/itunes/7496",
            "secondary_langs": ["pt"],
        },
        "EuroNews": {
            "aliases": ["EuroNews"],
            "uri": "youtube.channel.live//https://www.youtube.com/@euronewspt/live",
            "secondary_langs": ["pt"],
            "world_news": True,
        },
    },
}


def _prov(config=None):
    prov = NewsMediaProvider(config)
    prov._archive = {k: {kk: dict(vv) for kk, vv in v.items()}
                     for k, v in _FAKE_DB.items()}
    return prov


def test_instantiation():
    prov = NewsMediaProvider()
    assert prov.name == "news"


def test_bundled_db_loads():
    """The shipped News.json parses and is non-empty."""
    prov = NewsMediaProvider()
    assert isinstance(prov.archive, dict)
    assert len(prov.archive) > 0


def test_search_accepts_context_kwargs():
    """The provider accepts the pipeline's request-context kwargs."""
    prov = _prov()
    results = prov.search(
        Signals(medium=MediaType.RADIO, title="NPR"),
        lang="en-us",
        supported_playback_types={"audio"},
        blocked_genres={"adult"},
        region="US",
        session_id="sess-1",
    )
    assert all(isinstance(r, Release) for r in results)
    assert results


def test_search_by_name_returns_release_with_extractor_uri():
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO, title="NPR"),
                          lang="en-us", region="US")
    assert results
    top = results[0]
    assert isinstance(top, Release)
    assert top.work.title == "NPR"
    assert top.work.media_type == MediaType.RADIO
    assert top.uri.startswith("news//")
    assert top.stream_mode == StreamMode.LIVE
    assert 0.0 <= top.match_confidence <= 1.0


def test_releases_tagged_as_news_programme_format():
    """News is a mediavocab ProgrammeFormat (1.0 moved it off the genre axis)."""
    from mediavocab import ProgrammeFormat
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO, title="news"),
                          lang="en-us")
    assert results
    assert all(r.work.programme_format == ProgrammeFormat.NEWS for r in results)


def test_search_filters_foreign_language():
    """en-us request should not surface pt-PT feeds."""
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO, title="news"),
                          lang="en-us")
    titles = {r.work.title for r in results}
    assert "RTP" not in titles


def test_search_matches_requested_language():
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO, title="RTP"),
                          lang="pt-pt")
    assert any(r.work.title == "RTP" for r in results)


def test_search_results_sorted_by_confidence():
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO, title="NPR"),
                          lang="en-us", region="US")
    confs = [r.match_confidence for r in results]
    assert confs == sorted(confs, reverse=True)


def test_search_swallows_errors():
    prov = _prov()
    with patch.object(prov, "_read_db", side_effect=RuntimeError("boom")):
        assert prov.search(Signals(medium=MediaType.RADIO, title="x")) == []


def test_music_typed_query_returns_nothing():
    """A MUSIC browse/search request is outside SERVED_MEDIA -> []."""
    prov = _prov()
    assert prov.search(Signals(medium=MediaType.MUSIC)) == []
    assert prov.search(Signals(medium=MediaType.MUSIC, title="play some music")) == []


def test_radio_typed_query_returns_results():
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.RADIO), lang="en-us")
    assert results


def test_untyped_browse_returns_low_confidence_results():
    """A bare browse (no title, no medium) still gets news, but at the
    browse convention (~0.5), not inflated to a near-1.0 self-match."""
    prov = _prov()
    results = prov.search(Signals(), lang="en-us")
    assert results
    assert all(r.match_confidence <= 0.7 for r in results)


def test_generic_medium_browse_returns_results():
    prov = _prov()
    results = prov.search(Signals(medium=MediaType.GENERIC), lang="en-us")
    assert results
