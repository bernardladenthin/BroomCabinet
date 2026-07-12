package de.fraunhofer.fokus.jackpot.test.binaryMessage;

import static org.junit.Assert.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.junit.Test;

import de.fraunhofer.fokus.jackpot.test.Common;
import de.fraunhofer.fokus.jackpot.util.BinaryMessage;

public class TestBinaryMessage {

    private BinaryMessage recreate(BinaryMessage bm) throws IOException {
        final ByteArrayOutputStream baos = new ByteArrayOutputStream();
        final DataOutputStream dOut = new DataOutputStream(baos);
        bm.toDataOutput(dOut);

        final byte[] bytes = baos.toByteArray();

        final ByteArrayInputStream bais = new ByteArrayInputStream(bytes);
        final DataInputStream dIn = new DataInputStream(bais);

        final BinaryMessage recreated = BinaryMessage.fromDataInputJava8(dIn);
        return recreated;
    }

    @Test
    public void roundTripHeartbeat() throws IOException {
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1l);

        final BinaryMessage recreated = recreate(bm);

        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
    }

    @Test
    public void roundTripSignalMessagesReceived() throws IOException {
        final List<Long> testList = new ArrayList<>(Arrays.asList(1l, 2l, 3l, 4l, 5l));
        final BinaryMessage bm = BinaryMessage.createAcknowledged(1l, testList);

        final BinaryMessage recreated = recreate(bm);

        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
    }

    @Test
    public void roundTripBox() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.simpleByteArray,
            Common.simpleSettingsCompression
        );

        final BinaryMessage recreated = recreate(bm);

        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
    }

    @Test
    public void roundTripBoxCompressionGZIP() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.simpleByteArray,
            Common.alwaysGZIPSettingsCompression
        );

        assertTrue(Common.errorNotGZIPUsed, bm.isGzipUsed());
        final BinaryMessage recreated = recreate(bm);
        assertTrue(Common.errorNotGZIPUsed, recreated.isGzipUsed());

        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
    }

    @Test
    public void roundTripBoxCompressionLZ4() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.simpleByteArray,
            Common.alwaysLZ4SettingsCompression
        );

        assertTrue(Common.errorNotLZ4Used, bm.isLz4Used());
        final BinaryMessage recreated = recreate(bm);
        assertTrue(Common.errorNotLZ4Used, recreated.isLz4Used());

        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
    }
}
