// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.binaryMessage;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.lessThan;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.notNullValue;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.test.Common;
import net.ladenthin.jackpot.util.BinaryMessage;

public class BinaryMessageTest {

    /**
     * Serializes the given message through {@link BinaryMessage#toDataOutput} and reads it
     * back through {@link BinaryMessage#fromDataInputJava8}, mimicking the wire round trip.
     */
    private BinaryMessage recreate(BinaryMessage bm) throws IOException {
        final ByteArrayOutputStream baos = new ByteArrayOutputStream();
        final DataOutputStream dOut = new DataOutputStream(baos);
        bm.toDataOutput(dOut);

        final byte[] bytes = baos.toByteArray();

        final ByteArrayInputStream bais = new ByteArrayInputStream(bytes);
        final DataInputStream dIn = new DataInputStream(bais);

        return BinaryMessage.fromDataInputJava8(dIn);
    }

    // <editor-fold defaultstate="collapsed" desc="wire round trip">
    @Test
    public void fromDataInputJava8_heartbeatWritten_recreatedEqualsOriginal() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1L);

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
    }

    @Test
    public void fromDataInputJava8_acknowledgedWritten_recreatedEqualsOriginal() throws IOException {
        // arrange
        final List<Long> testList = new ArrayList<>(Arrays.asList(1L, 2L, 3L, 4L, 5L));
        final BinaryMessage bm = BinaryMessage.createAcknowledged(1L, testList);

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
    }

    @Test
    public void fromDataInputJava8_uncompressedMessageWritten_recreatedEqualsOriginal() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.simpleByteArray,
            Common.simpleSettingsCompression
        );

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
    }

    @Test
    public void fromDataInputJava8_gzipCompressedMessageWritten_recreatedEqualsOriginalAndKeepsFlag() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.simpleByteArray,
            Common.alwaysGZIPSettingsCompression
        );

        // pre-assert
        assertThat(Common.errorNotGZIPUsed, bm.isGzipUsed(), is(true));

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotGZIPUsed, recreated.isGzipUsed(), is(true));
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
    }

    @Test
    public void fromDataInputJava8_lz4CompressedMessageWritten_recreatedEqualsOriginalAndKeepsFlag() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.simpleByteArray,
            Common.alwaysLZ4SettingsCompression
        );

        // pre-assert
        assertThat(Common.errorNotLZ4Used, bm.isLz4Used(), is(true));

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotLZ4Used, recreated.isLz4Used(), is(true));
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
    }

    @Test
    public void fromDataInputJava8_emptyMessageWritten_recreatedUnboxesToEmptyArray() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            new byte[0],
            Common.simpleSettingsCompression
        );

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertThat(Common.errorNotTheSame, recreated, is(equalTo(bm)));
        assertArrayEquals(new byte[0], recreated.unbox(Common.simpleSettingsCompression));
    }

    @Test
    public void fromDataInputJava8_gzipCompressedEmptyMessage_unboxesToEmptyArray() throws IOException {
        // arrange: force compression even for a zero-length payload (the shared alwaysTrue
        // fixture matches only length >= 1, so empty payloads skip compression there)
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            new byte[0],
            Common.gzipEvenWhenEmptySettingsCompression
        );

        // pre-assert
        assertThat(Common.errorNotGZIPUsed, bm.isGzipUsed(), is(true));

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertArrayEquals(new byte[0], recreated.unbox(Common.gzipEvenWhenEmptySettingsCompression));
    }

    @Test
    public void fromDataInputJava8_lz4CompressedEmptyMessage_unboxesToEmptyArray() throws IOException {
        // arrange: force compression even for a zero-length payload (the shared alwaysTrue
        // fixture matches only length >= 1, so empty payloads skip compression there)
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            new byte[0],
            Common.lz4EvenWhenEmptySettingsCompression
        );

        // pre-assert
        assertThat(Common.errorNotLZ4Used, bm.isLz4Used(), is(true));

        // act
        final BinaryMessage recreated = recreate(bm);

        // assert
        assertArrayEquals(new byte[0], recreated.unbox(Common.lz4EvenWhenEmptySettingsCompression));
    }

    @Test
    public void fromDataInputJava8_extremeIdsWritten_recreatedEqualsOriginal() throws IOException {
        // arrange
        final BinaryMessage minimum = BinaryMessage.createHeartbeat(Long.MIN_VALUE);
        final BinaryMessage maximum = BinaryMessage.createHeartbeat(Long.MAX_VALUE);

        // act, assert
        assertThat(Common.errorNotTheSame, recreate(minimum), is(equalTo(minimum)));
        assertThat(Common.errorNotTheSame, recreate(maximum), is(equalTo(maximum)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="box compression selection">
    @Test
    public void box_gzipConditionDoesNotMatch_gzipNotUsedAndContentPreserved() throws IOException {
        // arrange, act
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.simpleByteArray,
            Common.gzipNeverMatchSettingsCompression
        );

        // assert
        assertThat(Common.errorGZIPUsed, bm.isGzipUsed(), is(false));
        assertArrayEquals(Common.simpleByteArray, bm.unbox(Common.gzipNeverMatchSettingsCompression));
    }

    @Test
    public void box_lz4ConditionDoesNotMatch_lz4NotUsedAndContentPreserved() throws IOException {
        // arrange, act
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.simpleByteArray,
            Common.lz4NeverMatchSettingsCompression
        );

        // assert
        assertThat(Common.errorLZ4Used, bm.isLz4Used(), is(false));
        assertArrayEquals(Common.simpleByteArray, bm.unbox(Common.lz4NeverMatchSettingsCompression));
    }

    @Test
    public void box_gzipResultNotSmallerThanTinyInput_gzipSkippedAndContentPreserved() throws IOException {
        // arrange: the GZIP container overhead makes a 1-byte payload grow, not shrink

        // act
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.tinyByteArray,
            Common.gzipRequireSmallerSettingsCompression
        );

        // assert
        assertThat(Common.errorGZIPUsed, bm.isGzipUsed(), is(false));
        assertArrayEquals(Common.tinyByteArray, bm.unbox(Common.gzipRequireSmallerSettingsCompression));
    }

    @Test
    public void box_lz4ResultNotSmallerThanTinyInput_lz4SkippedAndContentPreserved() throws IOException {
        // arrange: the LZ4 block overhead makes a 1-byte payload grow, not shrink

        // act
        final BinaryMessage bm = BinaryMessage.box(
            1L,
            Common.tinyByteArray,
            Common.lz4RequireSmallerSettingsCompression
        );

        // assert
        assertThat(Common.errorLZ4Used, bm.isLz4Used(), is(false));
        assertArrayEquals(Common.tinyByteArray, bm.unbox(Common.lz4RequireSmallerSettingsCompression));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="state guards">
    @Test
    public void isLz4Used_heartbeatState_throwsException() {
        // arrange
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1L);

        // act, assert
        assertThrows(IllegalStateException.class, bm::isLz4Used);
    }

    @Test
    public void isGzipUsed_heartbeatState_throwsException() {
        // arrange
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1L);

        // act, assert
        assertThrows(IllegalStateException.class, bm::isGzipUsed);
    }

    @Test
    public void getAcknowledged_heartbeatState_throwsException() {
        // arrange
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1L);

        // act, assert
        assertThrows(IllegalStateException.class, bm::getAcknowledged);
    }

    @Test
    public void isStateHeartbeat_heartbeatCreated_onlyHeartbeatStateActive() {
        // arrange
        final BinaryMessage bm = BinaryMessage.createHeartbeat(1L);

        // act, assert
        assertThat(bm.isStateHeartbeat(), is(true));
        assertThat(bm.isStateMessage(), is(false));
        assertThat(bm.isStateAcknowledged(), is(false));
    }

    @Test
    public void isLz4Used_acknowledgedState_throwsException() {
        // arrange
        final BinaryMessage bm = BinaryMessage.createAcknowledged(1L, Arrays.asList(1L));

        // act, assert
        assertThrows(IllegalStateException.class, bm::isLz4Used);
    }

    @Test
    public void getAcknowledged_acknowledgedState_returnsUnmodifiableListWithSameContent() {
        // arrange
        final List<Long> testList = new ArrayList<>(Arrays.asList(1L, 2L, 3L));
        final BinaryMessage bm = BinaryMessage.createAcknowledged(1L, testList);

        // act
        final List<Long> acknowledged = bm.getAcknowledged();

        // pre-assert
        assertThat(acknowledged, is(notNullValue()));

        // assert
        assertThat(acknowledged, is(equalTo(testList)));
        assertThrows(UnsupportedOperationException.class, () -> acknowledged.add(4L));
    }

    @Test
    public void getAcknowledged_messageState_throwsException() throws IOException {
        // arrange
        final BinaryMessage bm = BinaryMessage.box(1L, Common.simpleByteArray, Common.simpleSettingsCompression);

        // act, assert
        assertThrows(IllegalStateException.class, bm::getAcknowledged);
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="equals, hashCode, compareTo, toString">
    @Test
    public void equals_sameContentBoxedTwice_messagesAreEqualWithSameHashCode() throws IOException {
        // arrange
        final BinaryMessage a = BinaryMessage.box(1L, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage sameContent = BinaryMessage.box(1L, Common.simpleByteArray, Common.simpleSettingsCompression);

        // act, assert
        assertThat(a, is(equalTo(sameContent)));
        assertThat(sameContent, is(equalTo(a)));
        assertThat(a.hashCode(), is(equalTo(sameContent.hashCode())));
    }

    @Test
    public void equals_differentIdOrContent_messagesAreNotEqual() throws IOException {
        // arrange
        final BinaryMessage a = BinaryMessage.box(1L, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage differentId = BinaryMessage.box(2L, Common.simpleByteArray, Common.simpleSettingsCompression);
        final BinaryMessage differentContent = BinaryMessage.box(1L, Common.tinyByteArray, Common.simpleSettingsCompression);

        // act, assert
        assertThat(a, is(not(equalTo(differentId))));
        assertThat(a, is(not(equalTo(differentContent))));
        assertThat(a.equals(null), is(false));
        assertThat(a.equals("not a BinaryMessage"), is(false));
    }

    @Test
    public void compareTo_differentIds_ordersById() {
        // arrange
        final BinaryMessage low = BinaryMessage.createHeartbeat(-5L);
        final BinaryMessage mid = BinaryMessage.createHeartbeat(0L);
        final BinaryMessage high = BinaryMessage.createHeartbeat(5L);
        final List<BinaryMessage> messages = new ArrayList<>(Arrays.asList(high, low, mid));

        // act
        Collections.sort(messages);

        // assert
        assertThat(low.compareTo(mid), is(lessThan(0)));
        assertThat(high.compareTo(low), is(greaterThan(0)));
        assertThat(mid.compareTo(BinaryMessage.createHeartbeat(0L)), is(equalTo(0)));
        assertThat(messages, is(equalTo(Arrays.asList(low, mid, high))));
    }

    @Test
    public void toString_everyState_noExceptionThrown() throws IOException {
        // arrange
        final BinaryMessage heartbeat = BinaryMessage.createHeartbeat(1L);
        final BinaryMessage acknowledged = BinaryMessage.createAcknowledged(1L, Arrays.asList(1L));
        final BinaryMessage message = BinaryMessage.box(1L, Common.simpleByteArray, Common.simpleSettingsCompression);

        // act, assert
        assertThat(heartbeat.toString(), is(notNullValue()));
        assertThat(acknowledged.toString(), is(notNullValue()));
        assertThat(message.toString(), is(notNullValue()));
    }
    // </editor-fold>
}
