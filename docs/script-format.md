# Script Format

ClipScript videos are described with JSON.

## Root Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `title` | string | yes | Internal video title. |
| `output` | string | yes | MP4 output path, relative to the script file. |
| `template` | string | yes | Template path, relative to the script file. |
| `voiceover` | string[] | yes | One voiceover line per scene. |
| `scenes` | object[] | yes | Ordered scene list. |

`voiceover.length` must match `scenes.length`.

## Paths

Paths inside a script are resolved relative to the script file:

- `output`
- `template`
- video scene `src`

Paths inside a template, such as `logo`, are resolved relative to the template file.

## Scene: `chat`

```json
{
  "type": "chat",
  "duration": 8,
  "chatHeader": false,
  "chatTitle": "Shared list",
  "chatSubtitle": "Two participants",
  "senderNames": false,
  "participantCount": 2,
  "messages": ["Message 1", "Message 2"]
}
```

## Scene: `title`

```json
{
  "type": "title",
  "duration": 1.5,
  "caption": "Sound familiar?"
}
```

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

## Scene: `outro`

```json
{
  "type": "outro",
  "duration": 3,
  "caption": "Make short demos from scripts",
  "url": "https://example.com"
}
```

`url` is optional.
