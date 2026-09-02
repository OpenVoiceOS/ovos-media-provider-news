"""News MediaProvider plugin for OVOS.

Exposes a curated catalog of broadcast-news audio feeds to the OCP pipeline as a
:class:`~ovos_plugin_manager.templates.media_provider.MediaProvider`. Replaces
the deprecated OCP search skill ``ovos-skill-news``.

The deprecated skill bundled a ``News.json`` database (feed name → uri / aliases
/ language / world-vs-local flag) and answered ``@ocp_search`` by fuzzy-matching
the spoken phrase against feed aliases, biasing by requested/native language and
user country, and returning ``MediaEntry``/``PluginStream`` objects whose URIs
carry an extractor prefix (``rss//``, ``news//``, ``youtube.channel.live//``).

This provider ports that catalog and matching logic: it ships the same
``News.json``, scores each feed against ``signals.title`` + ``lang`` + ``region``
and returns one :class:`mediavocab.Release` per matching feed, preserving the
original extractor-prefixed URI for the OCP playback layer to resolve.
"""
import json
from os.path import dirname, join
from typing import ClassVar, Dict, List, Optional, Set

from langcodes import closest_match
from ovos_utils.lang import standardize_lang_tag
from ovos_utils.log import LOG
from ovos_utils.parse import MatchStrategy, match_one

from mediavocab import MediaType, ProgrammeFormat, Release, Signals, StreamMode, Work

from ovos_plugin_manager.templates.media_provider import MediaProvider

from ovos_media_provider_news.version import __version__  # noqa: F401

NEWS_DB = join(dirname(__file__), "News.json")

# default feed per language (ported from ovos-skill-news)
LANG_DEFAULTS = {
    "pt-PT": "RTP", "es-ES": "RNE", "ca-ES": "CCMA", "en-GB": "BBC",
    "en-US": "NPR", "en-AU": "ABC", "en-CA": "CBC", "it-IT": "GR1",
    "fr-FR": "EuroNews", "de-DE": "DLF - Die Nachrichten",
}


class NewsMediaProvider(MediaProvider):
    """Search the curated news-feed catalog and return playable releases."""

    name: ClassVar[str] = "news"

    # every Release this provider builds carries work.media_type == RADIO
    # (mediavocab has no dedicated NEWS MediaType; news is a ProgrammeFormat
    # layered on top of the RADIO carrier type, see _entry_to_release).
    SERVED_MEDIA: ClassVar[Set[MediaType]] = {MediaType.RADIO}

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.default_feed: Optional[str] = self.config.get("default_feed")
        self._archive: Optional[Dict] = None

    @property
    def archive(self) -> Dict:
        if self._archive is None:
            try:
                with open(NEWS_DB) as f:
                    self._archive = json.load(f)
            except Exception:
                LOG.exception("Failed to load bundled News.json")
                self._archive = {}
        return self._archive

    def _read_db(self, target_langs: List[str], world_only: bool = False,
                 local_only: bool = False) -> List[dict]:
        """Yield feed configs filtered by language / world-vs-local flag."""
        entries: List[dict] = []
        for lang, feeds in self.archive.items():
            std_lang = standardize_lang_tag(lang)
            if target_langs:
                lang_score = closest_match(std_lang, target_langs)[-1]
                if lang_score > 10:
                    continue
            default_feed = self.default_feed or LANG_DEFAULTS.get(lang)
            for feed, cfg in feeds.items():
                if world_only and not cfg.get("world_news", False):
                    continue
                if local_only and cfg.get("world_news"):
                    continue
                cfg = dict(cfg)
                cfg["lang"] = std_lang
                cfg["title"] = cfg.get("title") or feed
                cfg["is_default"] = feed == default_feed
                entries.append(cfg)
        return entries

    @staticmethod
    def _score(title: str, entry: dict, target_langs: List[str],
               region: Optional[str], base: float = 0.0) -> float:
        """Relevance 0.0-1.0 for a feed (ported from the skill scorer).

        A bare browse request (no ``title``) has nothing to fuzzy-match
        against, so it is not scored as if it did: it sits at the browse
        convention (``base``, ~0.5) with only the lang/region/default bonuses
        layered on. Only an actual title match earns the fuzzy-scaled score.
        """
        score = base
        if not title:
            entry_lang = standardize_lang_tag(entry["lang"])
            entry_langs = {standardize_lang_tag(l)
                           for l in entry.get("secondary_langs", [])}
            entry_langs.add(entry_lang)
            if region and any(l.endswith(f"-{region.lower()}") for l in entry_langs):
                score += 0.10
            if entry.get("is_default"):
                score += 0.05
            return max(0.0, min(score, 1.0))

        _, alias_score = match_one(
            title,
            entry.get("aliases") or [entry["title"]],
            strategy=MatchStrategy.TOKEN_SORT_RATIO)
        score += alias_score * 0.5

        entry_lang = standardize_lang_tag(entry["lang"])
        entry_langs = {standardize_lang_tag(l)
                       for l in entry.get("secondary_langs", [])}
        entry_langs.add(entry_lang)
        if target_langs:
            if any(l in target_langs for l in entry_langs):
                score += 0.30
            else:
                score -= 0.20
        if region and any(l.endswith(f"-{region.lower()}") for l in entry_langs):
            score += 0.20
        if entry.get("is_default"):
            score += 0.10
        return max(0.0, min(score, 1.0))

    @staticmethod
    def _entry_to_release(entry: dict, score: float) -> Release:
        """Bridge a news-feed config to a :class:`mediavocab.Release`.

        The extractor-prefixed URI (``rss//…``, ``news//…``,
        ``youtube.channel.live//…``) is preserved verbatim for the OCP playback
        layer to resolve.
        """
        # News is a structural programme format (mediavocab 1.0 moved it out of
        # the genre axis); the carrier media type stays RADIO.
        work = Work(title=entry.get("title") or "", media_type=MediaType.RADIO,
                    programme_format=ProgrammeFormat.NEWS)
        return Release(
            work=work,
            uri=entry.get("uri") or "",
            image=entry.get("image") or "",
            stream_mode=StreamMode.LIVE,
            match_confidence=score,
            extra={k: v for k, v in {
                "world_news": entry.get("world_news", False),
                "lang": entry.get("lang"),
            }.items() if v is not None},
        )

    def search(self, signals: Signals, lang: str = "en-us", *,
               supported_playback_types: Optional[Set[str]] = None,
               blocked_genres: Optional[Set[str]] = None,
               region: Optional[str] = None,
               session_id: Optional[str] = None) -> List[Release]:
        """Score the curated news catalog against ``signals.title`` / ``lang`` /
        ``region`` and return one :class:`Release` per matching feed, ranked by
        confidence.

        A bare NEWS request (no title) browses the catalog (default feeds
        float to the top, at the browse-convention confidence, ~0.5).
        A query naming a concrete media type outside ``SERVED_MEDIA`` (e.g.
        MUSIC) cannot be served by this provider and returns ``[]`` — a
        query with no type (GENERIC/unset) may still legitimately get news.
        Returns ``[]`` on failure.
        """
        medium = signals.medium
        if medium is not None and medium not in (MediaType.GENERIC,) \
                and medium not in self.SERVED_MEDIA:
            return []
        try:
            title = (signals.title or "").strip()
            target_langs = [standardize_lang_tag(lang)] if lang else []
            base = 0.5 if not title else 0.0  # browse convention

            results: List[Release] = []
            for entry in self._read_db(target_langs):
                score = self._score(title, entry, target_langs, region,
                                    base=base)
                if score < 0.5:
                    continue
                results.append(self._entry_to_release(entry, score))

            results.sort(key=lambda r: r.match_confidence, reverse=True)
            return results
        except Exception:
            LOG.exception("News search failed")
            return []
