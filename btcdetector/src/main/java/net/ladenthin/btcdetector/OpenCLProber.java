package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddressesOpenCL;

public class OpenCLProber extends Prober {

    private final ProbeAddressesOpenCL probeAddressesOpenCL;
    private final ByteBufferUtility byteBufferUtility = new ByteBufferUtility(false);

    public OpenCLProber(ProbeAddressesOpenCL probeAddressesOpenCL) {
        super(probeAddressesOpenCL);
        this.probeAddressesOpenCL = probeAddressesOpenCL;
    }

    @Override
    public void run() {
        initLMDB();
        addSchutdownHook();
        startStatisticsTimer();
    }

}
