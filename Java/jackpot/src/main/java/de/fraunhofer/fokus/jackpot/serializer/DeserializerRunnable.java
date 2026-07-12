package de.fraunhofer.fokus.jackpot.serializer;

import java.util.concurrent.Callable;

import de.fraunhofer.fokus.jackpot.configuration.SettingsCompression;
import de.fraunhofer.fokus.jackpot.deserializer.Deserializer;
import de.fraunhofer.fokus.jackpot.util.BinaryMessage;

public class DeserializerRunnable<T> implements Callable<T> {

    /**
     * The {@link DeserializerFactory}-
     */
    private final DeserializerFactory<T> deserializerFactory;

    private final BinaryMessage bm;

    private final SettingsCompression settingsCompression;

    public DeserializerRunnable(
        final DeserializerFactory<T> deserializerFactory,
        final BinaryMessage bm,
        final SettingsCompression settingsCompression
    ) {
        this.deserializerFactory = deserializerFactory;
        this.bm = bm;
        this.settingsCompression = settingsCompression;
    }

    /**
     * {@inheritDoc} This method serialize and box the message.
     * @throws java.lang.Exception
     */
    @Override
    public T call() throws Exception {
        byte[] bytes = bm.unbox(settingsCompression);
        Deserializer<T> deserializer = deserializerFactory.getDeserializer(bytes);
        return deserializer.deserialize();
    }

}
