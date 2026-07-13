// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.security.InvalidParameterException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.zip.Deflater;

import org.junit.jupiter.api.Test;

import net.ladenthin.jackpot.configuration.BooleanCondition;
import net.ladenthin.jackpot.configuration.CLZ4Compressor;
import net.ladenthin.jackpot.configuration.CLZ4Decompressor;
import net.ladenthin.jackpot.configuration.CompressCondition;
import net.ladenthin.jackpot.configuration.ConditionGZIP;
import net.ladenthin.jackpot.configuration.ConditionLZ4;
import net.ladenthin.jackpot.configuration.SettingsCompression;

/**
 * {@link SettingsCompression}'s constructor guards against three inconsistent configurations
 * (see its three {@code InvalidParameterException} checks). This class pins each guard plus
 * the happy paths they protect.
 */
public class SettingsCompressionTest {

    /**
     * A condition matching every non-negative length; content of the condition is irrelevant
     * for the constructor guards under test.
     */
    private static final CompressCondition ALWAYS_MATCH = new CompressCondition(BooleanCondition.greaterEqual, 0, false);

    /**
     * A single-entry GZIP condition list for enabling GZIP legally.
     */
    private static final List<ConditionGZIP> GZIP_CONDITIONS =
        Arrays.asList(new ConditionGZIP(Deflater.BEST_SPEED, ALWAYS_MATCH));

    /**
     * A single-entry LZ4 condition list for enabling LZ4 legally.
     */
    private static final List<ConditionLZ4> LZ4_CONDITIONS =
        Arrays.asList(new ConditionLZ4(CLZ4Compressor.unsafeFastCompressor, ALWAYS_MATCH));

    /**
     * The default GZIP decompression buffer size used across these fixtures. Unit: [bytes].
     */
    private static final int GZIP_BUFFER_SIZE = 2048;

    // <editor-fold defaultstate="collapsed" desc="constructor guards">
    @Test
    public void constructor_gzipAndLz4BothEnabled_throwsException() {
        // act, assert
        assertThrows(InvalidParameterException.class, () -> new SettingsCompression(
            GZIP_CONDITIONS, LZ4_CONDITIONS, true, true, GZIP_BUFFER_SIZE, CLZ4Decompressor.safeFastDecompressor));
    }

    @Test
    public void constructor_gzipEnabledWithoutConditions_throwsException() {
        // act, assert
        assertThrows(InvalidParameterException.class, () -> new SettingsCompression(
            null, null, true, false, GZIP_BUFFER_SIZE, null));
    }

    @Test
    public void constructor_lz4EnabledWithoutConditions_throwsException() {
        // act, assert
        assertThrows(InvalidParameterException.class, () -> new SettingsCompression(
            null, null, false, true, GZIP_BUFFER_SIZE, CLZ4Decompressor.safeFastDecompressor));
    }

    /**
     * A buffer size below one would make {@link net.ladenthin.jackpot.util.BinaryMessage#unbox}
     * loop forever on a GZIP-compressed message ({@code GZIPInputStream.read} with a
     * zero-length buffer returns 0, never -1), so it must be rejected at configuration time.
     */
    @Test
    public void constructor_gzipBufferSizeZero_throwsException() {
        // act, assert
        assertThrows(InvalidParameterException.class, () -> new SettingsCompression(
            null, null, false, false, 0, null));
    }

    @Test
    public void constructor_gzipBufferSizeNegative_throwsException() {
        // act, assert
        assertThrows(InvalidParameterException.class, () -> new SettingsCompression(
            null, null, false, false, -1, null));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="valid configurations">
    @Test
    public void constructor_gzipEnabledWithConditions_configurationAccepted() {
        // arrange, act
        final SettingsCompression settings =
            new SettingsCompression(GZIP_CONDITIONS, null, true, false, GZIP_BUFFER_SIZE, null);

        // assert
        assertThat(settings.enableGZIP, is(true));
        assertThat(settings.enableLZ4, is(false));
        assertThat(settings.gzipConditions, hasSize(1));
    }

    @Test
    public void constructor_lz4EnabledWithConditions_configurationAccepted() {
        // arrange, act
        final SettingsCompression settings =
            new SettingsCompression(null, LZ4_CONDITIONS, false, true, GZIP_BUFFER_SIZE, CLZ4Decompressor.safeFastDecompressor);

        // assert
        assertThat(settings.enableLZ4, is(true));
        assertThat(settings.enableGZIP, is(false));
        assertThat(settings.lz4Conditions, hasSize(1));
    }

    @Test
    public void constructor_bothDisabled_nullConditionListsAccepted() {
        // arrange, act
        final SettingsCompression settings =
            new SettingsCompression(null, null, false, false, GZIP_BUFFER_SIZE, null);

        // assert
        assertThat(settings.enableGZIP, is(false));
        assertThat(settings.enableLZ4, is(false));
    }

    @Test
    public void constructor_noArguments_producesDisabledSafeDefault() {
        // arrange, act
        final SettingsCompression settings = new SettingsCompression();

        // assert
        assertThat(settings.enableGZIP, is(false));
        assertThat(settings.enableLZ4, is(false));
        assertThat(settings.gzipBufferSize, is(equalTo(GZIP_BUFFER_SIZE)));
        assertThat(settings.decompressor, is(equalTo(CLZ4Decompressor.safeFastDecompressor)));
    }
    // </editor-fold>

    // <editor-fold defaultstate="collapsed" desc="defensive copy">
    @Test
    public void constructor_mutableConditionListGiven_listIsDefensivelyCopiedAndImmutable() {
        // arrange
        final List<ConditionGZIP> mutableSource = new ArrayList<>(GZIP_CONDITIONS);
        final SettingsCompression settings =
            new SettingsCompression(mutableSource, null, true, false, GZIP_BUFFER_SIZE, null);

        // act: mutating the source list after construction must not affect the settings
        mutableSource.add(new ConditionGZIP());

        // assert
        assertThat("SettingsCompression must copy the list, not alias it",
            settings.gzipConditions, hasSize(1));
        assertThrows(UnsupportedOperationException.class,
            () -> settings.gzipConditions.add(new ConditionGZIP()));
    }
    // </editor-fold>
}
