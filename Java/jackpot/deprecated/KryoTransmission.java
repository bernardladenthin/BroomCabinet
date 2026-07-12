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
package de.fraunhofer.fokus.jackpot.transceiver;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Type;

import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;

import de.fraunhofer.fokus.jackpot.configuration.SettingsGZIP;
import de.fraunhofer.fokus.jackpot.message.TMessage;

/**
 * Kryo implementation of a transmission.
 * WARNING: Kryo fails randomly:
 * http://code.google.com/p/kryo/issues/detail?id=57
 * https://groups.google.com/forum/?fromgroups=#!topic/kryo-users/oKpqe7uPXfI
 * and
 * Kryo Output/Input String deserialization failed in heavy load application
 * after 3 hours running
 * http://code.google.com/p/kryo/issues/detail?id=102
 * 
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 * @deprecated Kryo transmission fails randomly.
 * @date 03/25/2013
 */
public class KryoTransmission<T> extends DataStreamTransmission<T>
	implements Transmission<T> {

	private final Kryo kryo = new Kryo();
	private final static int bufferSize = 4096;

	public KryoTransmission(
		final BufferedInputStream in,
		final BufferedOutputStream out,
		final Type typeOfMessage,
		final SettingsGZIP settingsGZIP
	) {
		super(in, out, typeOfMessage, settingsGZIP);
	}

	@SuppressWarnings("unchecked")
	@Override
	public TMessage<T> read() throws Exception {
		final byte[] b = readByte();
		final ByteArrayInputStream inStream = new ByteArrayInputStream(b);
		final Input input = new Input(inStream, bufferSize);
		final Object readObject = kryo.readClassAndObject(input);
		TMessage<T> object = null;

		if(readObject == null) {
			throw new NullPointerException();
		}

		if(typeObject.getClass().isInstance(readObject)) {
			object = (TMessage<T>) readObject;
		} else {
			throw new IllegalArgumentException();
		}

		inStream.close();
		return object;
	}

	@Override
	public void write(final TMessage<T> object) throws Exception {
		final ByteArrayOutputStream outStream = new ByteArrayOutputStream();
		final Output output = new Output(outStream, bufferSize);
		try {
			kryo.writeClassAndObject(output, object);
		} finally {
			// close() also calls flush()
			output.close();
		}
		writeByte(outStream.toByteArray());
	}

}

