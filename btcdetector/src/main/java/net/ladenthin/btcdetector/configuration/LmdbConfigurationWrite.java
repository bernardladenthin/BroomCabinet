package net.ladenthin.btcdetector.configuration;

public class LmdbConfigurationWrite extends LmdbConfigurationReadOnly {
    // delete empty addresses
    public boolean deleteEmptyAddresses = true;

    // LMDB size in MiB (e.g. 10240)
    public int mapSizeInMiB = 10240;
}
