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

import java.lang.reflect.Type;

/**
 * Main session based configuration for {@link de.fraunhofer.fokus.jackpot.Tranceiver}.
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
     * <code>initialMessageId+1</code>.
     */
    public final long initialMessageId = Long.MIN_VALUE;

    /**
     * The last message has the id <code>lastMessageId-1</code>.
     */
    public final long lastMessageId = Long.MAX_VALUE;

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
    }
}
