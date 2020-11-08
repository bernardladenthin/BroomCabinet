package net.ladenthin.btcdetector;

import java.io.IOException;
import java.nio.ByteBuffer;
import org.junit.Before;
import org.junit.Test;
import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.*;

public class AddressFileTest {

    private static final TestAddresses testAddresses = new TestAddresses(0, false);

    private static final String SEGWIT_PUBLIC_ADDRESS = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq";

    StaticKey staticKey = new StaticKey();

    @Before
    public void init() throws IOException {
    }

    @Test
    public void fromBase58CSVLine_TestUncompressed() throws IOException {
        // act
        ByteBuffer byteBuffer = new AddressFile(testAddresses.networkParameters).fromBase58CSVLine(staticKey.publicKeyUncompressed);

        // assert
        assertThat(byteBuffer, is(equalTo(staticKey.byteBufferPublicKeyUncompressed)));
    }

    @Test
    public void fromBase58CSVLine_TestCompressed() throws IOException {
        // act
        ByteBuffer byteBuffer = new AddressFile(testAddresses.networkParameters).fromBase58CSVLine(staticKey.publicKeyCompressed);

        // assert
        assertThat(byteBuffer, is(equalTo(staticKey.byteBufferPublicKeyCompressed)));
    }

    @Test
    public void fromBase58CSVLine_addressLineIsEmpty_returnNull() throws IOException {
        // act
        ByteBuffer byteBuffer = new AddressFile(testAddresses.networkParameters).fromBase58CSVLine("");

        // assert
        assertThat(byteBuffer, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressLineStartsWithIgnoreLineSign_returnNull() throws IOException {
        // act
        ByteBuffer byteBuffer = new AddressFile(testAddresses.networkParameters).fromBase58CSVLine(AddressFile.IGNORE_LINE_PREFIX + " test");

        // assert
        assertThat(byteBuffer, is(nullValue()));
    }

    @Test
    public void fromBase58CSVLine_addressStartsWithbc1_returnNull() throws IOException {
        // act
        ByteBuffer byteBuffer = new AddressFile(testAddresses.networkParameters).fromBase58CSVLine(SEGWIT_PUBLIC_ADDRESS);

        // assert
        assertThat(byteBuffer, is(nullValue()));
    }

}
