// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import java.util.concurrent.Callable;

import net.ladenthin.jackpot.configuration.SettingsCompression;
import net.ladenthin.jackpot.util.BinaryMessage;

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
