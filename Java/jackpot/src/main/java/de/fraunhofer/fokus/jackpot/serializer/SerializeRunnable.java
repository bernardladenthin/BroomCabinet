package de.fraunhofer.fokus.jackpot.serializer;

import java.util.concurrent.Callable;

import de.fraunhofer.fokus.jackpot.configuration.SettingsCompression;
import de.fraunhofer.fokus.jackpot.util.BinaryMessage;

public class SerializeRunnable<T> implements Callable<BinaryMessage> {

    private final SerializerFactory<T> serializerFactory;
    private final long id;
    private final T msg;
    private final SettingsCompression settingsCompression;

    public SerializeRunnable(final SerializerFactory<T> serializerFactory, final long id,
        final T msg, final SettingsCompression settingsCompression) {
        this.serializerFactory = serializerFactory;
        this.id = id;
        this.msg = msg;
        this.settingsCompression = settingsCompression;
    }

    /**
     * {@inheritDoc} This method serialize and box the message.
     * @throws java.lang.Exception
     */
    @Override
    public BinaryMessage call() throws Exception {
        return BinaryMessage.box(id, serializerFactory.getSerializer(msg).serialize(), settingsCompression);
    }

}
