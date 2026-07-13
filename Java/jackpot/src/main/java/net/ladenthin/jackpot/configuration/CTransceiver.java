// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.configuration;

import java.io.Serializable;

/**
 * Base configuration for {@link net.ladenthin.jackpot.Transceiver}.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class CTransceiver implements Serializable {

    private static final long serialVersionUID = -1640741624029229950L;

    /**
     * Type of the serialization.
     */
    public final SerializationType serialization;

    /**
     * Type of the deserialization.
     */
    public final SerializationType deserialization;

    /**
     * Type of the connection.
     */
    public final ConnectionType connectionType;

    /**
     * Settings to compress a object.
     */
    public final SettingsCompression settingsCompression;

    /**
     * Configures how the connection should be setup. (Client/Server, Socket/Pipe etc.).
     */
    public CConnector connector;

    /**
     * Heartbeat settings.
     */
    public Heartbeat heartbeat;

    /**
     * Defines the id-range of generated messages.
     */
    public CMessageIdLong messageIdLong;

    /**
     * The default {@link #maxPayloadLength}. Unit: [bytes].
     */
    public static final int DEFAULT_MAX_PAYLOAD_LENGTH = 64 * 1024 * 1024;

    /**
     * Upper bound for a single message payload, enforced on BOTH sides: the sender rejects
     * oversized serialized messages (surfaced as a
     * {@link net.ladenthin.jackpot.message.TError}; the wire sequence stays intact), and the
     * receiver rejects frames claiming more — a corrupt or malicious length would otherwise
     * allocate gigabytes and kill the reader with an OutOfMemoryError. Both sides of a
     * connection should configure the same value. Unit: [bytes].
     */
    public int maxPayloadLength = DEFAULT_MAX_PAYLOAD_LENGTH;

    /**
     * Complete constructor, this contains all possible configuration options.
     * @param serialization
     * @param deserialization
     * @param connectionType
     * @param settingsGZIP
     * @param connector
     * @param heartbeat
     * @param messageIdLong 
     */
    public CTransceiver(
        final SerializationType serialization,
        final SerializationType deserialization,
        final ConnectionType connectionType,
        final SettingsCompression settingsGZIP,
        final CConnector connector,
        final Heartbeat heartbeat,
        final CMessageIdLong messageIdLong
    ) {
        this.serialization = serialization;
        this.deserialization = deserialization;
        this.connectionType = connectionType;
        this.settingsCompression = settingsGZIP;
        this.connector = connector;
        this.heartbeat = heartbeat;
        this.messageIdLong = messageIdLong;
    }

    /**
     * Minimal configuration for the transceiver,
     * this uses defaults for all other possible settings.
     * @param connectionType
     * @param connector 
     */
    public CTransceiver(final ConnectionType connectionType, final CConnector connector) {
        this.serialization      = SerializationType.ObjectOutputStreamSerialization;
        this.deserialization    = SerializationType.ObjectOutputStreamSerialization;
        this.connectionType     = connectionType;
        this.settingsCompression = new SettingsCompression();
        this.connector          = connector;
        this.heartbeat          = new Heartbeat();
        this.messageIdLong      = new CMessageIdLong();
    }
}
