// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.sendAndReceive;

/**
 * A message whose {@link java.io.ObjectOutputStream} serialization deterministically fails:
 * it carries a field of a type that does not implement {@link java.io.Serializable}, so
 * {@code writeObject} throws {@link java.io.NotSerializableException}. It extends
 * {@link SimpleMessage} so it passes the transceiver's message-class check and reaches the
 * serialization pipeline.
 */
public class UnserializableMessage extends SimpleMessage {

    private static final long serialVersionUID = 1L;

    /**
     * Not {@link java.io.Serializable} — the poison pill that makes serialization fail.
     */
    @SuppressWarnings("unused")
    private final Object unserializableContent = new Object();

    public UnserializableMessage(byte[] binaryContent) {
        super(binaryContent);
    }
}
