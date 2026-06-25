# ovos-media-provider-news

OVOS **MediaProvider** plugin for broadcast news feeds. Replaces the deprecated
OCP search skill
[`ovos-skill-news`](https://github.com/OpenVoiceOS/ovos-skill-news).

Instead of broadcasting `ovos.common_play.query` over the bus and waiting for
skills to answer, the OCP pipeline loads MediaProvider plugins in-process, gates
them by routing, and calls `search()` directly. This plugin ships a curated
`News.json` catalog (feed name → uri / aliases / language / world-vs-local
flag) and scores each feed against the query title, request language and region,
returning [`mediavocab.Release`](https://github.com/TigreGotico/mediavocab)
objects.

Feed URIs keep their original extractor prefix (`rss//…`, `news//…`,
`youtube.channel.live//…`) so the OCP playback layer resolves them exactly as
the deprecated skill did.

## Install

```bash
pip install ovos-media-provider-news
```

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

## License

Apache-2.0
