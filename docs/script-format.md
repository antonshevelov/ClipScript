# Script Format

ClipScript videos are JSON documents validated against strict Schema v1.

## Root Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `schemaVersion` | `1` | yes | Current script schema version. |
| `title` | string | yes | Internal video name. |
| `output` | string | yes | MP4 output path, relative to the script file. |
| `template` | string | yes | Template path, relative to the script file. |
| `scenes` | object[] | yes | Ordered scene definitions. |

Each scene can include an optional non-empty `voiceover` string. Scenes without it do not call TTS. Unknown fields are rejected, as are string-to-number coercion, invalid duration/start/end/fps/resolution values, and invalid crops.

## Paths

Script `output`, `template`, and video `src` paths resolve relative to the script file. Template `logo` resolves relative to the template file.

## Scene: `chat`

```json
{
  "type": "chat",
  "duration": 8,
  "voiceover": "Optional narration for this scene",
  "chatHeader": false,
  "chatTitle": "Shared list",
  "chatSubtitle": "Two participants",
  "senderNames": false,
  "participantCount": 2,
  "messages": ["Message 1", "Message 2"]
}
```

`duration` and a non-empty `messages` list are required. `participantCount` is `2` or `3`.

## Scene: `title`

```json
{
  "type": "title",
  "duration": 1.5,
  "caption": "Sound familiar?",
  "voiceover": "Sound familiar?"
}
```

`duration` and `caption` are required.

## Scene: `video`

```json
{
  "type": "video",
  "src": "../assets/app-demo.mp4",
  "start": 0,
  "end": 10,
  "crop": [100, 0, 984, 1920],
  "backgroundColor": "#f9fcf9",
  "caption": "Use a real screen recording"
}
```

`src` and either `duration` or `end` are required. `start` defaults to `0`; `end` must exceed `start`. Crop is `[x1, y1, x2, y2]` with non-negative values and `x2 > x1`, `y2 > y1`. A requested range past the source is rendered at the actual clamped source duration.

## Scene: `outro`

```json
{
  "type": "outro",
  "duration": 3,
  "caption": "Make short demos from scripts",
  "url": "https://example.com"
}
```

`duration` and `caption` are required. `url` is optional.

## Legacy 0.1.0 Scripts

Unversioned scripts remain accepted when they include the legacy root `voiceover` array. Its length must equal the number of scenes; the loader migrates each entry into matching scene-level `voiceover` before strict validation.

`examples/scripts/legacy-v0.json` is a runnable validation fixture for this compatibility path.

When `schemaVersion: 1` is present, root `voiceover` is forbidden. This is a format-level breaking change for new versioned scripts only. Existing scene types and both TTS providers are retained.
