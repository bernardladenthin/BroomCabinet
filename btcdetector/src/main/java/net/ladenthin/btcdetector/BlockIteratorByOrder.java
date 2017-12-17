package net.ladenthin.btcdetector;

import org.bitcoinj.core.Block;
import org.bitcoinj.core.Sha256Hash;
import org.bitcoinj.utils.BlockFileLoader;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;

/**
 * https://github.com/CounterpartyXCP/counterparty-lib/issues/374
 */
public class BlockIteratorByOrder {

    private final BlockFileLoader blockFileLoader;
    private final Iterator<Block> iterator;
    private final Map<Sha256Hash, Block> hashToBlock = new HashMap<>();
    private final Map<Sha256Hash, Sha256Hash> prevBlockHashToNextBlockHash = new HashMap<>();
    private final Set<Sha256Hash> orphanedBlocks;
    // 0000000000000000000000000000000000000000000000000000000000000000 is the hash before the genesis block
    private Sha256Hash lastRequestedBlockHash = Sha256Hash.wrap("0000000000000000000000000000000000000000000000000000000000000000");

    public BlockIteratorByOrder(BlockFileLoader blockFileLoader, Set<Sha256Hash> orphanedBlocks) {
        this.blockFileLoader = blockFileLoader;
        this.orphanedBlocks = orphanedBlocks;
        iterator = blockFileLoader.iterator();
    }

    public Block pop() {
        while(blocksAvailable()) {
            Block block = popIfAvailable();
            if (block != null) {
                return block;
            } else {
                pushNextToMap();
            }
        }
        return null;
    }

    private Block popIfAvailable() {
        Sha256Hash nextBlockHash = prevBlockHashToNextBlockHash.get(lastRequestedBlockHash);
        if (nextBlockHash != null) {
            // next block hash is in map
            prevBlockHashToNextBlockHash.remove(lastRequestedBlockHash);
            Block block = hashToBlock.get(nextBlockHash);
            hashToBlock.remove(nextBlockHash);
            lastRequestedBlockHash = block.getHash();
            return block;
        } else {
            return null;
        }
    }

    public boolean blocksAvailable() {
        return iterator.hasNext() || !hashToBlock.isEmpty();
    }

    private void pushNextToMap() {
        if(iterator.hasNext()) {
            Block block = iterator.next();
            Sha256Hash blockHash = block.getHash();
            if (orphanedBlocks.contains(blockHash)) {
                // found an orphaned block, dont push this block, push the next
                pushNextToMap();
                return;
            }
            hashToBlock.put(blockHash, block);
            prevBlockHashToNextBlockHash.put(block.getPrevBlockHash(), block.getHash());
        } else {
            throw new RuntimeException("No more blocks available to push. May you have unknown orphaned blocks in your chain. lastRequestedBlockHash: " + lastRequestedBlockHash + ", hashToBlock.keySet():" + hashToBlock.keySet());
        }
    }

}
