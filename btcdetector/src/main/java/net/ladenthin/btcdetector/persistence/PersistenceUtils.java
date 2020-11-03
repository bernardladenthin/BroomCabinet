package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.LegacyAddress;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.core.Sha256Hash;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;

public class PersistenceUtils {

    private final ByteBuffer emptyByteBuffer = ByteBuffer.allocateDirect(0).asReadOnlyBuffer();
    private final ByteBuffer zeroByteBuffer = longValueToByteBufferDirectAsReadOnlyBuffer(0L);

    private final NetworkParameters networkParameters;

    public PersistenceUtils(NetworkParameters networkParameters) {
        this.networkParameters = networkParameters;
    }

    public ByteBuffer longToByteBufferDirect(long longValue) {
        if (longValue == 0) {
            // use the cached zero value to reduce allocations
            return zeroByteBuffer;
        }
        ByteBuffer newValue = ByteBuffer.allocateDirect(Long.BYTES);
        newValue.putLong(longValue);
        newValue.flip();
        return newValue;
    }

    public ByteBuffer addressListToByteBufferDirect(List<LegacyAddress> addresses) {
        ByteBuffer byteBuffer = ByteBuffer.allocateDirect(LegacyAddress.LENGTH * addresses.size());
        for (LegacyAddress address : addresses) {
            byteBuffer.put(address.getHash160());
        }
        byteBuffer.flip();
        return byteBuffer;
    }

    public List<LegacyAddress> byteBufferToAddressList(ByteBuffer byteBuffer) {
        List<LegacyAddress> addresses = new ArrayList<>();
        int count = byteBuffer.remaining() / LegacyAddress.LENGTH;
        for (int i = 0; i < count; i++) {
            byte[] hash160 = new byte[LegacyAddress.LENGTH];
            byteBuffer.get(hash160);
            addresses.add(new LegacyAddress(networkParameters, hash160));
        }
        return addresses;
    }

    public LegacyAddress byteBufferToAddress(ByteBuffer byteBuffer) {
        return new LegacyAddress(networkParameters, byteBufferToBytes(byteBuffer));
    }

    public ByteBuffer addressToByteBufferDirect(LegacyAddress address) {
        return bytesToByteBufferDirect(address.getHash160());
    }

    public byte[] byteBufferToBytes(ByteBuffer byteBuffer) {
        byte[] bytes = new byte[byteBuffer.remaining()];
        byteBuffer.get(bytes);
        return bytes;
    }

    public ByteBuffer bytesToByteBufferDirect(byte[] bytes) {
        ByteBuffer key = ByteBuffer.allocateDirect(bytes.length);
        key.put(bytes).flip();
        return key;
    }

    public ByteBuffer hashToByteBufferDirect(Sha256Hash hash) {
        return bytesToByteBufferDirect(hash.getBytes());
    }

    public ByteBuffer longValueToByteBufferDirectAsReadOnlyBuffer(long value) {
        ByteBuffer byteBuffer = ByteBuffer.allocateDirect(Long.BYTES);
        byteBuffer.putLong(value);
        return byteBuffer.asReadOnlyBuffer();
    }
}
