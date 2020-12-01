package net.ladenthin.btcdetector.configuration;

public class ConsumerJava {
    public LmdbConfigurationReadOnly lmdbConfigurationReadOnly;
    public int printStatisticsEveryNSeconds = 60;
    public int threads = 1;
    public long delayEmptyConsumer = 10;
    public int queueSize = 100000;
}
