<!--
SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->
# jackpot

Transmit Java objects reliably over a stream (TCP socket or POSIX named pipe), with
pluggable serialization, optional compression, heartbeats, acknowledgements with automatic
resend, transparent reconnect, and dead-connection detection.

* Originally hosted on Google Code: <http://code.google.com/p/jackpot/> (Fraunhofer FOKUS, 2013–2014)
* GitHub mirror of the original: <https://github.com/fraunhoferfokus/jackpot>
* License: [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0)
* Java 8+, single Maven module (`net.ladenthin:jackpot`)

---

## Quick start

Both sides create a `Transceiver<T>` for the same message type. The `Transceiver` is a
`java.util.Observable`/`Observer`: you *observe it* to receive messages and errors, and you
*notify it* to send messages.

```java
// --- shared message type (must fit the configured serialization; here: Serializable) ---
public class ChatMessage implements Serializable {
    public final String text;
    public ChatMessage(String text) { this.text = text; }
}

// --- server side ---
CTransceiverSession serverSession = new CTransceiverSession(
    "chat-server",                                        // unique transceiver id (used in thread names)
    new TypeToken<ChatMessage>(){}.getType(),             // message type (gson TypeToken)
    ChatMessage.class,                                    // message class
    new CTransceiver(
        ConnectionType.ServerSocketConnection,
        new CConnector(new CServerSocketConnector(12345))
    )
);
Transceiver<ChatMessage> server = new Transceiver<>(serverSession);  // blocks until connected

// --- client side ---
CTransceiverSession clientSession = new CTransceiverSession(
    "chat-client",
    new TypeToken<ChatMessage>(){}.getType(),
    ChatMessage.class,
    new CTransceiver(
        ConnectionType.ClientSocketConnection,
        new CConnector(new CClientSocketConnector("localhost", 12345))
    )
);
Transceiver<ChatMessage> client = new Transceiver<>(clientSession);

// --- receive (typed convenience observer) ---
client.addObserver(new NanoObserver<>(ChatMessage.class, new NanoHandler<ChatMessage>() {
    @Override public void handleTransmission(ChatMessage m) { System.out.println(m.text); }
    @Override public void handleError(TError e)             { System.err.println(e); }
}));

// --- send (notify the transceiver; any Observable works, or call update directly) ---
client.update(null, new ChatMessage("hello"));

// --- shutdown (terminates every library thread) ---
TCommand shutdown = new TCommand();
shutdown.shutdown = true;
client.update(null, shutdown);
server.update(null, shutdown);
```

Note the `Transceiver` constructor starts connecting immediately; construct the server side
first (its connector listens), then the client.

---

## Feature overview

| Feature | Mechanism |
|---|---|
| Object transmission | Pluggable serialization: JDK `ObjectOutputStream` (default), Gson (JSON), Protostuff |
| Compression | Optional per-message GZIP **or** LZ4, rule-driven by payload size (`SettingsCompression`) |
| Ordering | Every wire message carries a strictly increasing 64-bit id; the receiver delivers in id order and buffers out-of-order arrivals |
| Reliability | Every written message is retained until the peer acknowledges it; unacknowledged messages are resent after `Heartbeat.resendInterval`; duplicates are discarded (and re-acknowledged) on the receiver |
| Keepalive | Heartbeat messages when the connection is idle (`Heartbeat.heartbeatInterval`) |
| Dead-connection detection | If nothing is received for `Heartbeat.connectionTimeout`, a `TError` with `expired = true` is surfaced (once per silence period) |
| Reconnect | A failed read/write transparently reconnects (up to 30 s, 5 s between attempts) and resumes; messages written into the dead connection are resent |
| Transports | TCP sockets (client/server), POSIX named pipes (FIFOs, Linux/Unix), Windows named pipes (kernel32 via JNA) |
| Error reporting | All failures surface as `TError` notifications to the observers (serialization failures, reconnect exhaustion, expiration) |
| Observability | `Transceiver.getUnacknowledgedMessageCount()` — near zero on a healthy connection; all library threads are named `jackpot-…` |
| Shutdown | A `TCommand` with `shutdown = true` terminates every library thread and closes the connector |

---

## Architecture

Each `Transceiver` owns a stack of layers, each with its own thread (all named
`jackpot-<Layer>-<transceiverId>`):

```
                    application
                        │ update(msg) / notifyObservers
                        ▼
                   Transceiver           (Observable/Observer facade, type check)
                        │
                   MessageLayer          (id generation, command handling)
                   ┌────┴────┐
             SerializeLayer  │           (parallel serialization pool, submission order kept)
                   │         │
                   ▼         ▼
                  WriteLayer            (write queue, heartbeats, ack batching,
                        │                retain-until-acknowledged + resend sweep)
                        ▼
                 ConnectionLayer        (streams, reconnect, liveness, pending acks)
                   ▲    │    ▲
        reader thread   │    └── Connector (ServerSocket/Socket/FIFO/Windows pipe)
                        ▼
                    ReadLayer           (strict id-order sequencing, duplicate discard,
                        │                ack bookkeeping, heartbeat/ack dispatch)
                        ▼
                 DeserializeLayer       (parallel deserialization pool, order kept)
                        │
                        ▼
                   Transceiver.notifyObservers(message)
```

### Wire protocol

Everything on the wire is a `BinaryMessage` in one of three states, serialized as:

```
int    flags          (bit 1: LZ4, bit 2: GZIP, bit 4: heartbeat, bit 8: acknowledged)
long   id             (strictly increasing per direction; both directions are independent)
-- state MESSAGE:
int    uncompressedSize
int    payloadLength
byte[] payload        (optionally GZIP- or LZ4-compressed serialized object)
-- state ACKNOWLEDGED:
int    count
long[] acknowledgedIds
-- state HEARTBEAT: (no body)
```

Heartbeats and acknowledgement messages occupy sequence ids like payload messages, so the
receiver's strict ordering covers them too — and the reliability machinery below can recover
any of them if lost.

### Reliability protocol

* **Sender:** every written message (payload, heartbeat, acknowledgement) is retained —
  *before* the write, so a write that dies mid-connection-loss is not lost — until the peer
  acknowledges its id. A sweep on idle ticks resends everything unacknowledged for longer
  than `Heartbeat.resendInterval`.
* **Receiver:** processes messages in strictly increasing id order (buffering ahead-of-time
  arrivals), acknowledges every processed message, discards already-processed duplicates and
  acknowledges them *again* (the duplicate means the sender never got the first
  acknowledgement).
* **Acknowledgements** are batched into one wire message and sent with priority; the
  writer is nudged at most once per `Heartbeat.heartbeatCheckInterval`, so the mutual
  acknowledgement-of-acknowledgement exchange idles at roughly one small message per second
  per direction instead of ping-ponging at network speed.
* A message lost on the wire (e.g. during a reconnect) wedges the receiver only until the
  sender's resend closes the id gap.

### Failure handling

| Failure | Behaviour |
|---|---|
| Serialization of one message fails | A heartbeat filling the already-allocated wire id keeps the stream consecutive; a `TError` with the stack trace is surfaced; later messages are unaffected |
| Deserialization of one message fails | The message is dropped, a `TError` is surfaced, later messages are unaffected |
| Connection drops | Reader/writer reconnect transparently (up to 30 s, 5 s between attempts); retained messages are resent; if reconnecting fails for good, a `TError` with `noConnectionPossible = true` is surfaced |
| Peer is transport-alive but silent | After `connectionTimeout` without any received message, a `TError` with `expired = true` is surfaced (once per silence period) |
| Shutdown (`TCommand.shutdown`) | All layer threads, pools and the heartbeat timer terminate; the connector (including a listening `ServerSocket`) is closed |

---

## Configuration reference

Everything is configured through immutable `C*` classes passed into `CTransceiverSession`.

### `CTransceiverSession`

| Field | Meaning |
|---|---|
| `transceiverId` | Unique name; appears in all thread names |
| `messageType` / `messageClass` | The transmitted type (Gson `TypeToken` type + class) |
| `transceiverConfiguration` | The `CTransceiver` below |
| `initialMessageId` / `lastMessageId` | Derived from `CMessageIdLong` (defaults: `Long.MIN_VALUE` / `Long.MAX_VALUE`) |

### `CTransceiver`

The minimal constructor `CTransceiver(ConnectionType, CConnector)` uses
`ObjectOutputStreamSerialization`, no compression, default `Heartbeat` and the full id range.
The full constructor lets you set:

| Field | Meaning | Default |
|---|---|---|
| `serialization` / `deserialization` | `ObjectOutputStreamSerialization`, `GsonSerialization`, `ProtostuffSerialization` | ObjectOutputStream |
| `connectionType` | `ServerSocketConnection`, `ClientSocketConnection`, `UnixNamedPipeServer/Client`, `WindowsNamedPipeServer/Client` | — |
| `settingsCompression` | see below | disabled |
| `connector` | the matching `C*Connector` inside a `CConnector` | — |
| `heartbeat` | see below | `new Heartbeat()` |
| `messageIdLong` | id range `begin`/`end`; both sides must configure the same `begin` | full `long` range |

### `Heartbeat`

| Field | Meaning | Default |
|---|---|---|
| `connectionTimeout` | silence duration after which the connection counts as dead (`TError.expired`) | 20000 ms |
| `heartbeatInterval` | idle time after which a heartbeat is sent (derived: `connectionTimeout / 2`) | 10000 ms |
| `heartbeatCheckInterval` | timer tick driving heartbeats, ack batching and the resend sweep (derived: `heartbeatInterval / 10`, at least 1 ms) | 1000 ms |
| `resendInterval` | retention time before an unacknowledged message is resent | 10000 ms |

Constructors: `Heartbeat()`, `Heartbeat(resendInterval)`,
`Heartbeat(resendInterval, connectionTimeout)`.

### `SettingsCompression`

Compression is rule-driven: a list of conditions (`ConditionGZIP` with a deflater level, or
`ConditionLZ4` with a `CLZ4Compressor` variant), each wrapping a `CompressCondition` — a
comparison (`BooleanCondition`: equal/greater/greaterEqual/lower/lowerEqual/notEqual) against
the payload length, plus `useOnlyIfCompressedLower` (skip compression when the result is not
actually smaller). Exactly one of GZIP/LZ4 may be enabled; enabling one requires its condition
list; `gzipBufferSize` must be ≥ 1; the `decompressor` (a `CLZ4Decompressor` variant) is
required to *receive* LZ4 messages — the default configuration
(`new SettingsCompression()`) is compression-off with `safeFastDecompressor` set.

The default `CompressCondition()` compresses payloads ≥ 1439 bytes (MTU-derived) only when
the compressed form is actually smaller.

### Connectors

| Config | Transport | Notes |
|---|---|---|
| `CServerSocketConnector(port[, soTimeout])` | listening TCP socket | `soTimeout` (default 20 s) bounds `accept()` and reads |
| `CClientSocketConnector(host, port[, soTimeout])` | outgoing TCP socket | `soTimeout` (default 20 s) bounds reads; a read timeout triggers a reconnect |
| `CUnixNamedPipeServerConnector(requestPipe, responsePipe)` | two POSIX FIFOs | server writes `requestPipe`, reads `responsePipe`; the client config swaps the two names |
| `CUnixNamedPipeClientConnector(requestPipe, responsePipe)` | two POSIX FIFOs | pipes are created with `mkfifo` if absent; FIFO open order is handled internally (server read-first, client write-first) |
| `CWindowsNamedPipeServerConnector(pipeName)` / `...Client...` | Windows named pipe | via JNA `kernel32` |

Ports are validated to `[0, 65535]`.

---

## Semantics and guarantees

* **Ordering:** messages are delivered to the application in exactly the order they were
  handed to `Transceiver.update` on the sending side (per direction).
* **Delivery:** at-least-once on the wire, exactly-once to the application — resends close
  loss gaps, duplicates are discarded by the receiver's sequencing.
* **Instances:** the received object is a deserialized *copy*, never the sent instance.
* **Mutability:** do not mutate a message after handing it to the transceiver — serialization
  runs in parallel; a concurrent mutation surfaces as a `TError` (the wire stream itself
  stays intact).
* **Threads:** delivery callbacks (`Observer.update`) run on library threads; keep them fast
  and never block them on the transceiver itself.
* **Memory:** the sender retains messages until acknowledged (`getUnacknowledgedMessageCount()`
  should hover near zero); the receiver buffers ahead-of-time arrivals until the gap closes.

## Known limitations

* One connection per `Transceiver`; both directions of one logical link need matching
  configurations (same serialization, same `messageIdLong.begin`).
* The receiver's ahead-of-time buffer and the sender's retain buffer are unbounded; a
  malicious or very bursty peer can grow them (bounded in practice by the resend/ack cycle).
* No TLS/authentication — run over trusted networks or tunnel.
* `java.util.Observable` is deprecated since Java 9 (the API still works; the library targets
  Java 8).
* Windows named pipes and the `noInAvailable` error flag are legacy paths without automated
  test coverage.
* The message id range does not wrap around: when `lastMessageId` is reached the transceiver
  surfaces errors instead of reusing ids (historical versions wrapped; the default full
  `long` range is practically inexhaustible, custom small ranges are not).
* A FIFO open can block indefinitely if the peer never opens its end (POSIX semantics); the
  socket transports bound everything with timeouts.

---

## Building and testing

```bash
mvn test         # full suite (unit + socket/pipe integration tests, JaCoCo report)
mvn package      # JAR
```

The JaCoCo coverage report lands in `target/site/jacoco/index.html`.

The integration tests bind localhost TCP ports 12345, 23456, 34567, 45678, 56789, 61234 and
create FIFOs under `target/`. The Unix pipe round trip runs on Linux only; the Windows pipe
round trip is disabled (needs a Windows host).

## History

Written 2013–2014 at Fraunhofer FOKUS (VSimRTI team) and continued by Bernard Ladenthin. In
2026 the library was overhauled: the acknowledgement/resend protocol was completed (it was
half-built and inactive), several pipeline hangs were fixed (serialization-failure id holes,
stale-duplicate wedges, a reconnect lock-ordering deadlock, shutdown thread leaks), the FIFO
transport's open-order deadlock was fixed, dead-connection detection was implemented, and the
test suite was rebuilt on JUnit Jupiter (120+ tests including live socket and FIFO round
trips).
