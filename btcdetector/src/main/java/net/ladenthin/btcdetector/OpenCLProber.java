package net.ladenthin.btcdetector;

import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import net.ladenthin.btcdetector.configuration.ProbeAddressesOpenCL;

public class OpenCLProber extends Prober {

    protected OpenCLProber(ProbeAddressesOpenCL probeAddressesOpenCL) {
        super(probeAddressesOpenCL);
    }

    @Override
    public void run() {
        throw new UnsupportedOperationException();
    }
}
