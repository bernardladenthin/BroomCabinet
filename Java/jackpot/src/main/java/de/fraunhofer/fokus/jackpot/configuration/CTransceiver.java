/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot.configuration;

import java.io.Serializable;

/**
 * Base configuration for {@link de.fraunhofer.fokus.jackpot.Transceiver}.
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
