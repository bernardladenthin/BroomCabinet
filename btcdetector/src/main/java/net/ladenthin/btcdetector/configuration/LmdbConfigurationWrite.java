package net.ladenthin.btcdetector.configuration;

public class LmdbConfigurationWrite extends LmdbConfigurationReadOnly {
    // delete empty addresses
    public boolean deleteEmptyAddresses = false;
    
    // LMDB size in MiB (e.g. 1024)
    public int mapSizeInMiB = 1;
}
