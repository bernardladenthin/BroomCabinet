// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import java.util.concurrent.Callable;

import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.deserializer.Deserializer;
import net.ladenthin.jackpot.util.BinaryMessage;

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
