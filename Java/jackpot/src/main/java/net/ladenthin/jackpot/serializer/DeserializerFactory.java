// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.serializer;

import net.ladenthin.jackpot.deserializer.Deserializer;

public interface DeserializerFactory<T> {

    Deserializer<T> getDeserializer(byte[] bytes);
}
