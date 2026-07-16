# PenShot Sidecar Contract Design

## Architecture

StoryMotion keeps ownership of its screenplay and storyboard domain models. A
`PenShotSidecarProvider` serializes a validated `ScreenplayPackage` into the
existing PenShot text form, submits it to an isolated HTTP sidecar, polls a
bounded task endpoint, and sends the untrusted result through
`adapt_penshot_result`. The provider never imports PenShot. The sidecar has its
own working directory, environment, dependencies, and process lifecycle.

The minimal protocol has three operations: submit with
`POST /v1/storyboards`, inspect with `GET /v1/tasks/{task_id}`, and cancel with
`DELETE /v1/tasks/{task_id}`. Submit returns `202` plus a task ID. Task status is
one of `pending`, `processing`, `completed`, `failed`, or `cancelled`.
Completed tasks must carry a raw PenShot-compatible result; failed tasks carry
a bounded error string. Unknown fields are ignored at the transport boundary,
while required fields and status/result combinations are validated strictly.

The HTTP client uses finite connect/read timeouts, a configurable poll interval
and an overall deadline. It accepts an injectable transport so unit tests do
not need a network server, while an integration test uses a loopback fake HTTP
server to prove the request paths, methods, and JSON shapes. A fallback provider
delegates to `RuleShotProvider` only for explicitly classified sidecar
availability, protocol, remote-task, and timeout failures. It does not hide
invalid StoryMotion inputs or programming errors.

This phase deliberately excludes authentication, Redis, production service
hosting, callbacks, batch submission, and direct PenShot execution. Those are
only justified after the contract and failure behavior pass locally.

