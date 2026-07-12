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
package de.fraunhofer.fokus.jackpot.deserializer;

import java.lang.reflect.Type;

/**
 * Abstract Deserializer.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @param <T>
 */
public abstract class Deserializer<T> {

    protected final Type messageType;
    protected final Class<?> messageClass;
    protected final byte[] bytes;

    // protected final T typeObject = new T();

    Deserializer(final Type messageType, Class<?> messageClass, final byte[] bytes) {
        this.messageType = messageType;
        this.messageClass = messageClass;
        this.bytes = bytes;
    }

    public abstract T deserialize() throws Exception;

}
