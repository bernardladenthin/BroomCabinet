package net.ladenthin.btcdetector.configuration;

import java.util.Set;

public class BlockchainAnalysis {
    public String blockchainDirectory;
    public String lastAnalyzedBlockHashFile;
    public LmdbConfigurationWrite lmdbConfigurationWrite;
    public Set<String> orphanedBlocks;
    public int printStatisticsEveryNSeconds;
}
