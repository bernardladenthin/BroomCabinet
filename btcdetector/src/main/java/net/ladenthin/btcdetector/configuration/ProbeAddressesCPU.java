package net.ladenthin.btcdetector.configuration;

public class ProbeAddressesCPU extends ProbeAddresses {
    public int producerThreads = 1;
    public int consumerThreads = 1;
    public long delayEmptyConsumer = 10;
    /**
     * Can be set to a lower value to improve a search on the puzzle transaction https://privatekeys.pw/puzzles/bitcoin-puzzle-tx
     * 1 can't be tested because {@link ECKey#fromPrivate} throws an {@link IllegalArgumentException}.
     */
    public int bitLength = 256;
    public int queueSize = 100000;
}
