package net.ladenthin.btcdetector.configuration;

public class ProbeAddressesCPU extends ProbeAddresses {
    public int producerThreads = 1;
    public int consumerThreads = 1;
    public long delayEmptyConsumer = 10;
}
