package de.fraunhofer.fokus.jackpot.test;

import java.util.Arrays;
import java.util.List;
import java.util.zip.Deflater;

import de.fraunhofer.fokus.jackpot.configuration.BooleanCondition;
import de.fraunhofer.fokus.jackpot.configuration.CLZ4Compressor;
import de.fraunhofer.fokus.jackpot.configuration.CompressCondition;
import de.fraunhofer.fokus.jackpot.configuration.ConditionGZIP;
import de.fraunhofer.fokus.jackpot.configuration.ConditionLZ4;
import de.fraunhofer.fokus.jackpot.configuration.SettingsCompression;
import de.fraunhofer.fokus.jackpot.test.binaryMessage.TestBinaryMessage;
import de.fraunhofer.fokus.jackpot.test.sendAndReceive.SimpleMessage;

public class Common {

    public final static byte[] simpleByteArray = TestBinaryMessage.class.getCanonicalName().getBytes();
    public final static SimpleMessage simpleMessage = new SimpleMessage(simpleByteArray);
    public final static String errorNotTheSame = "Message is not the same.";
    public final static String errorNotGZIPUsed = "GZIP is not used.";
    public final static String errorNotLZ4Used = "LZ4 is not used.";
    public final static SettingsCompression simpleSettingsCompression = new SettingsCompression();
    public final static CompressCondition alwaysTrueCompressCondition = new CompressCondition(BooleanCondition.greaterEqual, 1, false);

    public final static List<ConditionGZIP> alwaysTrueGZIPCondition = Arrays.asList(
        new ConditionGZIP(
            Deflater.BEST_SPEED,
            Common.alwaysTrueCompressCondition
        )
    );

    public final static List<ConditionLZ4> alwaysTrueLZ4Condition = Arrays.asList(
        new ConditionLZ4(
            CLZ4Compressor.unsafeFastCompressor,
            Common.alwaysTrueCompressCondition
        )
    );

    public final static SettingsCompression alwaysGZIPSettingsCompression = new SettingsCompression(
        Arrays.asList(
            new ConditionGZIP(
                Deflater.BEST_SPEED,
                Common.alwaysTrueCompressCondition
            )
        ),
        null,
        true,
        false,
        2048,
        null
    );

    public final static SettingsCompression alwaysLZ4SettingsCompression = new SettingsCompression(
        null,
        Common.alwaysTrueLZ4Condition,
        false,
        true,
        2048,
        null
    );
}
