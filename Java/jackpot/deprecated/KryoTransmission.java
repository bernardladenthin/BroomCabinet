// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.transceiver;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Type;

import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;

import net.ladenthin.jackpot.configuration.SettingsGZIP;
import net.ladenthin.jackpot.message.TMessage;

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

