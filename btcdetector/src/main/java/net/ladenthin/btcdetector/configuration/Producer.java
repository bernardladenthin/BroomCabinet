package net.ladenthin.btcdetector.configuration;

public class Producer {
    /**
     * Can be set to a lower value to improve a search on the puzzle transaction https://privatekeys.pw/puzzles/bitcoin-puzzle-tx
     * <code>1</code> can't be tested because {@link ECKey#fromPrivate} throws an {@link IllegalArgumentException}.
     * Range: {@code 2} to {@code 256}.
     */
    public int privateKeyBitLength = 256;
}
