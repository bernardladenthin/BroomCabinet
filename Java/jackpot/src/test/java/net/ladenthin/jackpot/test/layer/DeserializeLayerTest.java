// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.layer;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;

import com.google.gson.reflect.TypeToken;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectOutputStream;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

import net.ladenthin.jackpot.DeserializeLayer;
import net.ladenthin.jackpot.ErrorLayer;
import net.ladenthin.jackpot.configuration.CClientSocketConnector;
import net.ladenthin.jackpot.configuration.CConnector;
import net.ladenthin.jackpot.configuration.CTransceiver;
import net.ladenthin.jackpot.configuration.CTransceiverSession;
import net.ladenthin.jackpot.configuration.ConnectionType;
import net.ladenthin.jackpot.message.TError;
import net.ladenthin.jackpot.messageprocessing.ParallelErrorInformant;
import net.ladenthin.jackpot.messageprocessing.SequentialMessageReceiver;
import net.ladenthin.jackpot.test.Common;
import net.ladenthin.jackpot.test.sendAndReceive.SimpleMessage;
import net.ladenthin.jackpot.util.BinaryMessage;

/**
 * Edge cases of the {@link DeserializeLayer}: a payload that cannot be deserialized (wire
 * corruption, incompatible class) must surface as a {@link TError} — and must NOT kill the
 * loop thread or affect later, valid messages. No socket involved; messages are fed directly
 * through {@link DeserializeLayer#dataAvailable}.
 */
public class DeserializeLayerTest {

    /**
     * Upper bound for the polls in this test. Unit: [ms].
     */
    private static final long WAIT_TIMEOUT_MILLIS = 5000;

    /**
     * Poll interval. Unit: [ms].
     */
    private static final long POLL_INTERVAL_MILLIS = 10;

    private DeserializeLayer<SimpleMessage> deserializeLayer;

    private final List<SimpleMessage> received = new CopyOnWriteArrayList<>();
    private volatile TError lastError;

    @BeforeEach
    public void setUp() {
        final CTransceiverSession session = new CTransceiverSession(
            "deserializeLayerTest",
            new TypeToken<SimpleMessage>() {}.getType(),
            SimpleMessage.class,
            new CTransceiver(
                ConnectionType.ClientSocketConnection,
                // never connected: messages are fed directly
                new CConnector(new CClientSocketConnector("localhost", 1))
            )
        );

        final ErrorLayer errorLayer = new ErrorLayer(new ParallelErrorInformant() {
            @Override
            public void informError(TError error) {
                lastError = error;
            }
        });

        deserializeLayer = new DeserializeLayer<>(session, errorLayer,
            new SequentialMessageReceiver<SimpleMessage>() {
                @Override
                public void receiveMessage(SimpleMessage tm) {
                    received.add(tm);
                }
            });
    }

    @AfterEach
    public void tearDown() {
        deserializeLayer.shutdownRunnable();
    }

    /**
     * Serializes the message the same way the ObjectOutputStream serializer does.
     */
    private byte[] serialize(SimpleMessage message) throws IOException {
        try (ByteArrayOutputStream bos = new ByteArrayOutputStream();
             ObjectOutputStream out = new ObjectOutputStream(bos)) {
            out.writeObject(message);
            out.flush();
            return bos.toByteArray();
        }
    }

    // <editor-fold defaultstate="collapsed" desc="dataAvailable edge cases">
    @Test
    @Timeout(30)
    public void dataAvailable_payloadIsGarbage_errorSurfacedAndLoopKeepsWorking() throws Exception {
        // arrange: a payload that is no valid ObjectOutputStream data
        final BinaryMessage garbage = BinaryMessage.box(
            1L, new byte[] {1, 2, 3}, Common.simpleSettingsCompression);
        final SimpleMessage validMessage = new SimpleMessage(Common.simpleByteArray);
        final BinaryMessage valid = BinaryMessage.box(
            2L, serialize(validMessage), Common.simpleSettingsCompression);

        // act: garbage first, then a valid message
        deserializeLayer.dataAvailable(garbage);
        deserializeLayer.dataAvailable(valid);

        // assert: the valid message is still delivered (the loop survived) ...
        final long deadline = System.currentTimeMillis() + WAIT_TIMEOUT_MILLIS;
        while (received.isEmpty() && System.currentTimeMillis() < deadline) {
            Thread.sleep(POLL_INTERVAL_MILLIS);
        }
        assertThat("The valid message after the garbage payload was never delivered.",
            received, hasSize(1));
        assertThat(received.get(0), is(equalTo(validMessage)));

        // ... and the garbage payload surfaced as an error, not silently swallowed
        assertThat("The undeserializable payload was never surfaced as an error.",
            lastError, is(notNullValue()));
    }
    // </editor-fold>
}
