// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.lang.reflect.Type;

/**
 * Main session based configuration for {@link net.ladenthin.jackpot.Tranceiver}.
 * 
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class CTransceiverSession {

    /**
     * The transmitterId is a unique identifier for each transmitter instance.
     */
    public final String transceiverId;

    /**
     * This value indicates a message never send/received. The first message has the id
     * <code>initialMessageId+1</code>. Taken from the configured {@link CMessageIdLong#begin}
     * (default: {@link Long#MIN_VALUE}).
     */
    public final long initialMessageId;

    /**
     * The last message has the id <code>lastMessageId-1</code>. Taken from the configured
     * {@link CMessageIdLong#end} (default: {@link Long#MAX_VALUE}).
     */
    public final long lastMessageId;

    /**
     * The type of the transmitted message.
     */
    public final Type messageType;

    /**
     * The class of the transmitted message.
     */
    public final Class<?> messageClass;

    /**
     * Base configuration containing information about the way messages are send/received through
     * the {@link Transceiver}
     */
    public final CTransceiver transceiverConfiguration;

    /**
     * @param transceiverId Unique id for the transceiver instance.
     * @param messageType   The type of the message.
     * @param messageClass  The Transceiver configuration.
     * @param transceiverConfiguration
     */
    public CTransceiverSession(final String transceiverId, final Type messageType,
        final Class<?> messageClass, final CTransceiver transceiverConfiguration
    ) {
        this.transceiverId = transceiverId;
        this.messageType = messageType;
        this.messageClass = messageClass;
        this.transceiverConfiguration = transceiverConfiguration;

        /**
         * Respect the configured message id range (historically it was hardcoded and the
         * {@link CMessageIdLong} configuration was silently ignored).
         */
        if (transceiverConfiguration != null && transceiverConfiguration.messageIdLong != null) {
            this.initialMessageId = transceiverConfiguration.messageIdLong.begin;
            this.lastMessageId = transceiverConfiguration.messageIdLong.end;
        } else {
            this.initialMessageId = Long.MIN_VALUE;
            this.lastMessageId = Long.MAX_VALUE;
        }
    }
}
