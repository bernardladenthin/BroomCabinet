// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.test.configuration;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import java.security.InvalidParameterException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.zip.Deflater;

import org.junit.Test;

import net.ladenthin.jackpot.configuration.BooleanCondition;
import net.ladenthin.jackpot.configuration.CLZ4Compressor;
import net.ladenthin.jackpot.configuration.CLZ4Decompressor;
import net.ladenthin.jackpot.configuration.CompressCondition;
import net.ladenthin.jackpot.configuration.ConditionGZIP;
import net.ladenthin.jackpot.configuration.ConditionLZ4;
import net.ladenthin.jackpot.configuration.SettingsCompression;

/**
 * {@link SettingsCompression}'s constructor guards against three inconsistent configurations
 * (see its three {@code InvalidParameterException} checks). None of them had a test: every
 * existing fixture only ever builds valid configurations. This class pins each guard plus the
 * happy paths they protect.
 */
public class TestSettingsCompression {

    private static final CompressCondition ALWAYS_MATCH = new CompressCondition(BooleanCondition.greaterEqual, 0, false);

    private static final List<ConditionGZIP> GZIP_CONDITIONS =
        Arrays.asList(new ConditionGZIP(Deflater.BEST_SPEED, ALWAYS_MATCH));

    private static final List<ConditionLZ4> LZ4_CONDITIONS =
        Arrays.asList(new ConditionLZ4(CLZ4Compressor.unsafeFastCompressor, ALWAYS_MATCH));

    @Test(expected = InvalidParameterException.class)
    public void rejectsGZIPAndLZ4BothEnabled() {
        new SettingsCompression(GZIP_CONDITIONS, LZ4_CONDITIONS, true, true, 2048, CLZ4Decompressor.safeFastDecompressor);
    }

    @Test(expected = InvalidParameterException.class)
    public void rejectsGZIPEnabledWithoutConditions() {
        new SettingsCompression(null, null, true, false, 2048, null);
    }

    @Test(expected = InvalidParameterException.class)
    public void rejectsLZ4EnabledWithoutConditions() {
        new SettingsCompression(null, null, false, true, 2048, CLZ4Decompressor.safeFastDecompressor);
    }

    @Test
    public void acceptsGZIPEnabledWithConditions() {
        final SettingsCompression settings =
            new SettingsCompression(GZIP_CONDITIONS, null, true, false, 2048, null);

        assertTrue(settings.enableGZIP);
        assertFalse(settings.enableLZ4);
        assertTrue(settings.gzipConditions.size() == 1);
    }

    @Test
    public void acceptsLZ4EnabledWithConditions() {
        final SettingsCompression settings =
            new SettingsCompression(null, LZ4_CONDITIONS, false, true, 2048, CLZ4Decompressor.safeFastDecompressor);

        assertTrue(settings.enableLZ4);
        assertFalse(settings.enableGZIP);
        assertTrue(settings.lz4Conditions.size() == 1);
    }

    @Test
    public void bothDisabledAllowsNullConditionLists() {
        final SettingsCompression settings = new SettingsCompression(null, null, false, false, 2048, null);

        assertFalse(settings.enableGZIP);
        assertFalse(settings.enableLZ4);
    }

    @Test
    public void noArgConstructorProducesADisabledSafeDefault() {
        final SettingsCompression settings = new SettingsCompression();

        assertFalse(settings.enableGZIP);
        assertFalse(settings.enableLZ4);
        assertTrue(settings.gzipBufferSize == 2048);
        assertTrue(settings.decompressor == CLZ4Decompressor.safeFastDecompressor);
    }

    @Test
    public void conditionListsAreDefensivelyCopiedAndImmutable() {
        final List<ConditionGZIP> mutableSource = new ArrayList<>(GZIP_CONDITIONS);
        final SettingsCompression settings =
            new SettingsCompression(mutableSource, null, true, false, 2048, null);

        mutableSource.add(new ConditionGZIP());
        assertTrue("SettingsCompression must copy the list, not alias it",
            settings.gzipConditions.size() == 1);

        try {
            settings.gzipConditions.add(new ConditionGZIP());
            fail("expected an immutable ImmutableList");
        } catch (UnsupportedOperationException expected) {
            // expected: com.google.common.collect.ImmutableList
        }
    }
}
