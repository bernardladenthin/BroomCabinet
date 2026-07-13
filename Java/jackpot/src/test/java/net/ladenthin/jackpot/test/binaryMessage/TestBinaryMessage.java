// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.binaryMessage;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.Test;

import net.ladenthin.jackpot.test.Common;
import net.ladenthin.jackpot.util.BinaryMessage;

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

    @Test
    public void roundTripBoxEmptyMessage() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            new byte[0],
            Common.simpleSettingsCompression
        );

        final BinaryMessage recreated = recreate(bm);
        assertTrue(Common.errorNotTheSame, bm.equals(recreated));
        assertArrayEquals(new byte[0], recreated.unbox(Common.simpleSettingsCompression));
    }

    @Test
    public void boxSkipsGZIPWhenConditionDoesNotMatch() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.simpleByteArray,
            Common.gzipNeverMatchSettingsCompression
        );

        assertFalse(Common.errorGZIPUsed, bm.isGzipUsed());
        assertArrayEquals(Common.simpleByteArray, bm.unbox(Common.gzipNeverMatchSettingsCompression));
    }

    @Test
    public void boxSkipsLZ4WhenConditionDoesNotMatch() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.simpleByteArray,
            Common.lz4NeverMatchSettingsCompression
        );

        assertFalse(Common.errorLZ4Used, bm.isLz4Used());
        assertArrayEquals(Common.simpleByteArray, bm.unbox(Common.lz4NeverMatchSettingsCompression));
    }

    @Test
    public void boxSkipsGZIPWhenCompressedResultIsNotSmaller() throws IOException {
        // the GZIP container overhead makes a 1-byte payload grow, not shrink
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.tinyByteArray,
            Common.gzipRequireSmallerSettingsCompression
        );

        assertFalse(Common.errorGZIPUsed, bm.isGzipUsed());
        assertArrayEquals(Common.tinyByteArray, bm.unbox(Common.gzipRequireSmallerSettingsCompression));
    }

    @Test
    public void boxSkipsLZ4WhenCompressedResultIsNotSmaller() throws IOException {
        // the LZ4 block overhead makes a 1-byte payload grow, not shrink
        final BinaryMessage bm = BinaryMessage.box(
            1l,
            Common.tinyByteArray,
            Common.lz4RequireSmallerSettingsCompression
        );

        assertFalse(Common.errorLZ4Used, bm.isLz4Used());
        assertArrayEquals(Common.tinyByteArray, bm.unbox(Common.lz4RequireSmallerSettingsCompression));
    }

    @Test
    public void heartbeatDoesNotExposeCompressionOrAcknowledgedState() throws IOException {
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1l);

        assertTrue(bm.isStateHeartbeat());
        assertFalse(bm.isStateMessage());
        assertFalse(bm.isStateAcknowledged());

        try {
            bm.isLz4Used();
            fail("expected IllegalStateException for isLz4Used() on a heartbeat message");
        } catch (IllegalStateException expected) {
            // expected
        }
        try {
            bm.isGzipUsed();
            fail("expected IllegalStateException for isGzipUsed() on a heartbeat message");
        } catch (IllegalStateException expected) {
            // expected
        }
        try {
            bm.getAcknowledged();
            fail("expected IllegalStateException for getAcknowledged() on a heartbeat message");
        } catch (IllegalStateException expected) {
            // expected
        }
    }

    @Test
    public void acknowledgedDoesNotExposeCompressionState() throws IOException {
        final List<Long> testList = new ArrayList<>(Arrays.asList(1l, 2l, 3l));
        final BinaryMessage bm = BinaryMessage.createAcknowledged(1l, testList);

        assertTrue(bm.isStateAcknowledged());
        assertFalse(bm.isStateMessage());
        assertFalse(bm.isStateHeartbeat());

        try {
            bm.isLz4Used();
            fail("expected IllegalStateException for isLz4Used() on an acknowledged message");
        } catch (IllegalStateException expected) {
            // expected
        }
        try {
            bm.isGzipUsed();
            fail("expected IllegalStateException for isGzipUsed() on an acknowledged message");
        } catch (IllegalStateException expected) {
            // expected
        }

        final List<Long> acknowledged = bm.getAcknowledged();
        assertEquals(testList, acknowledged);
        try {
            acknowledged.add(4l);
            fail("expected getAcknowledged() to return an unmodifiable list");
        } catch (UnsupportedOperationException expected) {
            // expected
        }
    }

    @Test
    public void messageDoesNotExposeAcknowledgedState() throws IOException {
        final BinaryMessage bm = BinaryMessage.box(1l, Common.simpleByteArray, Common.simpleSettingsCompression);

        assertTrue(bm.isStateMessage());

        try {
            bm.getAcknowledged();
            fail("expected IllegalStateException for getAcknowledged() on a plain message");
        } catch (IllegalStateException expected) {
            // expected
        }
    }

    @Test
    public void equalsAndHashCodeContract() throws IOException {
        final BinaryMessage a = BinaryMessage.box(1l, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage sameContent = BinaryMessage.box(1l, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage differentId = BinaryMessage.box(2l, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage differentContent = BinaryMessage.box(1l, Common.tinyByteArray, Common.simpleSettingsCompression);

        // reflexive
        assertEquals(a, a);
        // symmetric + same hash code for equal instances
        assertEquals(a, sameContent);
        assertEquals(sameContent, a);
        assertEquals(a.hashCode(), sameContent.hashCode());
        // differing id or content must not be equal
        assertNotEquals(a, differentId);
        assertNotEquals(a, differentContent);
        // null and foreign types
        assertNotEquals(a, null);
        assertNotEquals(a, "not a BinaryMessage");
    }

    @Test
    public void compareToOrdersById() throws IOException {
        final BinaryMessage low = BinaryMessage.createHeartbeat(-5l);
        final BinaryMessage mid = BinaryMessage.createHeartbeat(0l);
        final BinaryMessage high = BinaryMessage.createHeartbeat(5l);

        assertTrue(low.compareTo(mid) < 0);
        assertTrue(mid.compareTo(high) < 0);
        assertTrue(high.compareTo(low) > 0);
        assertEquals(0, mid.compareTo(BinaryMessage.createHeartbeat(0l)));

        final List<BinaryMessage> messages = new ArrayList<>(Arrays.asList(high, low, mid));
        Collections.sort(messages);
        assertEquals(Arrays.asList(low, mid, high), messages);
    }

    @Test
    public void roundTripExtremeIds() throws IOException {
        assertTrue(Common.errorNotTheSame,
            BinaryMessage.createHeartbeat(Long.MIN_VALUE).equals(recreate(BinaryMessage.createHeartbeat(Long.MIN_VALUE))));
        assertTrue(Common.errorNotTheSame,
            BinaryMessage.createHeartbeat(Long.MAX_VALUE).equals(recreate(BinaryMessage.createHeartbeat(Long.MAX_VALUE))));
    }

    @Test
    public void toStringDoesNotThrowForEveryState() throws IOException {
        assertNotNull(BinaryMessage.createHeartbeat(1l).toString());
        assertNotNull(BinaryMessage.createAcknowledged(1l, Arrays.asList(1l)).toString());
        assertNotNull(BinaryMessage.box(1l, Common.simpleByteArray, Common.simpleSettingsCompression).toString());
    }
}
