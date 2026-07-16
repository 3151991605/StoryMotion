# MiniMax Media Providers Design

## Scope

Build the smallest production-shaped media boundary needed to validate one
StoryMotion shot. The phase includes a synchronous MiniMax image provider and
an asynchronous Hailuo video provider. It excludes queues, callbacks, database
persistence, batch rendering, TTS, and UI.

## Alternatives

1. Put MiniMax HTTP calls directly in the demo pipeline. This is small but
   couples business logic to vendor payloads and makes failure testing hard.
2. Build generic StoryMotion contracts with one MiniMax implementation. This is
   selected: it preserves vendor replaceability without premature framework
   work.
3. Build a complete Redis/Celery media service now. This would support scale but
   is unnecessary for a one-shot course MVP validation.

## Components

`ImageGenerationRequest`, `GeneratedImage`, `VideoGenerationRequest`,
`VideoTask`, and `VideoResult` are strict StoryMotion models. `ImageProvider`
and `VideoProvider` are protocols owned by StoryMotion.

`MiniMaxImageProvider` calls `/v1/image_generation` with `image-01`, requests a
single base64 result, bounds decoded size, validates image magic bytes, and
writes the image locally. This avoids relying on a 24-hour image URL and allows
the saved first frame to be embedded as a data URL in the video request.

`HailuoVideoProvider` calls `/v1/video_generation`, maps the official statuses
`Preparing`, `Queueing`, `Processing`, `Success`, and `Fail` into StoryMotion
status values, then obtains file metadata from `/v1/files/retrieve`. It exposes
submit, single status check, result lookup, and download. Polling orchestration
is intentionally outside the provider so a future graph or task service owns
deadlines and cancellation.

## Failure and security boundaries

All request and response sizes are bounded. `base_resp.status_code` must be zero
even when HTTP status is 200. API keys exist only in Authorization headers and
are excluded from errors. Remote errors are normalized into transport,
protocol, account, and task failures. Downloads require HTTPS and an approved
MiniMax/Hailuo domain, reject credentials and non-standard ports, cap bytes,
and write through a temporary file before replacement.

There are no automatic image or video retries. A mock provider remains the
default for pipelines and demonstrations. The first live probe will use only
`shot_001`; it is a separate, explicit step because it may consume video quota.

## Official API basis

- Image: `POST /v1/image_generation`, model `image-01`, 9:16, base64 result.
- Video submit: `POST /v1/video_generation`, model `MiniMax-Hailuo-2.3`.
- Video query: `GET /v1/query/video_generation?task_id=...`.
- File metadata: `GET /v1/files/retrieve?file_id=...`.
