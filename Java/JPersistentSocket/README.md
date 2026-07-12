# JPersistentSocket

A partial prototype (originally 2014) of a **persistent, auto-reconnecting TCP
socket** that frames application data into acknowledged message blocks and
buffers them through a [`StreamBuffer`](https://github.com/bernardladenthin/streambuffer).

> **Status: incomplete prototype, kept for reference.** It compiles and builds
> green, but it is *not* a working socket end to end — several paths are still
> stubs (see below). It is preserved here as an example/archive, not as a
> library to depend on.

## Idea

An application writes bytes into an outbound `StreamBuffer`. A background thread
drains that buffer, chops it into fixed-size `TransmissionBlock`s (each carrying
a monotonically increasing id, an optional payload, and an optional list of
acknowledged ids), and writes them to the socket with `DataOutput`. If a write
fails, the socket transparently reconnects (`connectLoop`) within a configurable
time budget and resumes — so the connection *persists* across transient network
drops without the caller noticing.

## What is implemented

- **`TransmissionBlock`** — complete, symmetric wire framing
  (`writeBlock` / `readBlock`) plus `equals` / `hashCode` / `compareTo`. This is
  the one fully finished, self-contained, testable piece.
- **`connectLoop()`** — retry-until-deadline reconnect with per-attempt sleep.
- **`disconnect()`** — orderly teardown of all buffered streams and the socket.
- **`toSocketThread`** — drains the outbound `StreamBuffer` and produces blocks.
- **`writeThread`** — writes a block and triggers reconnect on `IOException`.
- **Configuration** value objects — `ClientSocket`, `ServerSocket`, `Connection`,
  `Configuration` (immutable).

## What is still a stub

- **Heartbeat** (`HeartbeatTask.run()`) — empty; no keep-alive is actually sent.
- **Inbound path** (`fromSocketThread`) — empty; nothing reads/reassembles
  incoming blocks.
- **`close()`** — throws `UnsupportedOperationException`.
- **`writeThread`** — runs a single iteration instead of looping.
- **`handleException()`** — swallows errors.
- **Tests** — only `TransmissionBlock` is covered (a write/read round-trip in
  `TransmissionBlockTest`); the socket paths themselves are untested.

## Changes made when moving it here

The original code (from Google Code) never compiled. To make it build under the
BroomCabinet `Java CI` (Temurin 21, `mvn clean verify`), the following were done
without altering the intended behaviour:

- `PersistentSocket` accessed fields directly on `Configuration` that actually
  live on its sub-objects — rerouted through the existing
  `getClientSocket()` / `getConnection()` getters.
- The `IOException` thrown by `connectLoop()` inside `writeThread` was unhandled
  — now caught and passed to `handleException`.
- New `pom.xml`: Java 17 release, JUnit 4.13.2, `streambuffer` **1.2.0** (latest),
  no GPG signing / Google Code / Travis leftovers.

## Build

```bat
mvn clean install
```
