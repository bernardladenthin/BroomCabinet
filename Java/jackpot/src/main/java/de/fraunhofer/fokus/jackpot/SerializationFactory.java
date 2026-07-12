package de.fraunhofer.fokus.jackpot;

import java.lang.reflect.Type;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.configuration.SerializationType;

public abstract class SerializationFactory {

    /**
     * Reference to the {@link CTransceiverSession}.
     */
    private final CTransceiverSession cTransceiverSession;

    /**
     * Short reference to the {@link SerializationType} for convenience and performance.
     */
    private final SerializationType transmissionType;

    /**
     * Short reference to the {@link Type} for convenience and performance.
     */
    private final Type messageType;

    /**
     * Short reference to the {@link Class} for convenience and performance.
     */
    private final Class<?> messageClass;

    public SerializationFactory(final CTransceiverSession cTransceiverSession) {
        this.cTransceiverSession = cTransceiverSession;

        this.transmissionType = this.cTransceiverSession.transceiverConfiguration.serialization;
        this.messageType = this.cTransceiverSession.messageType;
        this.messageClass = this.cTransceiverSession.messageClass;
    }

    public CTransceiverSession getcTransceiverSession() {
        return cTransceiverSession;
    }

    public SerializationType getTransmissionType() {
        return transmissionType;
    }

    public Type getMessageType() {
        return messageType;
    }

    public Class<?> getMessageClass() {
        return messageClass;
    }

}
