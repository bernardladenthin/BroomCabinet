// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

import net.ladenthin.jackpot.message.TError;

/**
 * Modern, typed callback interface for receiving messages and errors from a
 * {@link Transceiver} — the alternative to the deprecated {@link java.util.Observable}/
 * {@link java.util.Observer} facade (which keeps working unchanged alongside).
 *
 * <p>Register with {@link Transceiver#addListener(TransceiverListener)}. Callbacks run on
 * library threads: keep them fast and never block them on the transceiver itself. A
 * {@link RuntimeException} thrown by a callback is swallowed so it can neither kill the
 * delivering library thread nor starve the other listeners.
 *
 * @param <T> the message type of the {@link Transceiver}
 */
public interface TransceiverListener<T> {

    /**
     * A message arrived from the other side.
     *
     * @param message the received message (a deserialized copy, never the sent instance)
     */
    void onMessage(T message);

    /**
     * A failure was surfaced by the transceiver (serialization failure, reconnect
     * exhaustion, expiration, ...). Default: ignored, so message-only listeners stay a
     * single-method lambda.
     *
     * @param error the reported error
     */
    default void onError(TError error) {
        // intentionally ignored by default
    }
}
