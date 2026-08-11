# ovos-media-provider-news

This is an OVOS **MediaProvider** plugin for broadcast news feeds. It replaces the
deprecated OCP search skill [`ovos-skill-news`](https://github.com/OpenVoiceOS/ovos-skill-news).

The deprecated skill broadcast `ovos.common_play.query` over the bus and waited for
skills to answer. The OCP pipeline now loads MediaProvider plugins in-process, gates
them by routing, and calls `search()` directly.

This plugin ships a curated `News.json` catalog (feed name, uri, aliases, language,
and world-vs-local flag). It scores each feed against the query title, request
language, and region, and returns
[`mediavocab.Release`](https://github.com/TigreGotico/mediavocab) objects.

Feed URIs keep their original extractor prefix (`rss//…`, `news//…`,
`youtube.channel.live//…`), so the OCP playback layer resolves them exactly as the
deprecated skill did.

## Install

```bash
pip install ovos-media-provider-news
```

## Usage

The OCP pipeline discovers the plugin through its entry point and calls `search()`
with the parsed query signals:

```python
from ovos_media_provider_news import NewsMediaProvider
from mediavocab import Signals

provider = NewsMediaProvider()
results = provider.search(Signals(title="play the news"), lang="en-us")
```

A bare NEWS request with no title browses the catalog, and each language's default
feed floats to the top. The call returns an empty list on failure.

## Routing

| Axis | Value |
|------|-------|
| `media` | `NEWS` |
| `playback_type` | `AUDIO` |
| `genre_filter` | *(none)* |

## Entry point

```toml
[project.entry-points."opm.media.provider"]
news = "ovos_media_provider_news:NewsMediaProvider"
```

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `default_feed` | *(per-language default)* | Feed name to boost as the user's preferred station. |

## Related projects

- [OpenVoiceOS/ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager) loads and routes MediaProvider plugins for the OCP pipeline.
- [OpenVoiceOS/ovos-skill-news](https://github.com/OpenVoiceOS/ovos-skill-news) is the deprecated skill this plugin replaces.
- [TigreGotico/mediavocab](https://github.com/TigreGotico/mediavocab) defines the `Release` and `Signals` objects this plugin returns and consumes.

## License

Apache-2.0
