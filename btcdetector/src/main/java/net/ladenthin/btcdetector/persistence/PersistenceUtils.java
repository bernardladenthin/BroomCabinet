package net.ladenthin.btcdetector.persistence;

import org.bitcoinj.core.Address;
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

    public ByteBuffer addressListToByteBufferDirect(List<Address> addresses) {
        ByteBuffer byteBuffer = ByteBuffer.allocateDirect(Address.LENGTH * addresses.size());
        for (Address address : addresses) {
            byteBuffer.put(address.getHash160());
        }
        byteBuffer.flip();
        return byteBuffer;
    }

    public List<Address> byteBufferToAddressList(ByteBuffer byteBuffer) {
        List<Address> addresses = new ArrayList<>();
        int count = byteBuffer.remaining() / Address.LENGTH;
        for (int i = 0; i < count; i++) {
            byte[] hash160 = new byte[Address.LENGTH];
            byteBuffer.get(hash160);
            addresses.add(new Address(networkParameters, hash160));
        }
        return addresses;
    }

    public Address byteBufferToAddress(ByteBuffer byteBuffer) {
        return new Address(networkParameters, byteBufferToBytes(byteBuffer));
    }

    public ByteBuffer addressToByteBufferDirect(Address address) {
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
