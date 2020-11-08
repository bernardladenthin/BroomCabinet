package net.ladenthin.btcdetector.cli;

import com.google.gson.Gson;
import net.ladenthin.btcdetector.CPUProber;
import net.ladenthin.btcdetector.configuration.Command;
import net.ladenthin.btcdetector.configuration.Configuration;
import net.ladenthin.javacommons.StreamHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import net.ladenthin.btcdetector.AddressFilesToLMDB;
import net.ladenthin.btcdetector.AddressesExtractor;
import net.ladenthin.btcdetector.OpenCLProber;

// VM option: -Dorg.slf4j.simpleLogger.defaultLogLevel=trace
public class Main implements Runnable {

    private final static Logger logger = LoggerFactory.getLogger(Main.class);

    private final Configuration configuration;
    
    public Main(Configuration configuration) {
        this.configuration = configuration;
    }
    
    public static Main createFromConfigurationFile(File configFile) {
        try {
            return createFromConfigurationString(new StreamHelper().readFullyAsUTF8String(configFile));
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
    
    public static Main createFromConfigurationString(String configurationString) {
        Gson gson = new Gson();
        final Configuration configuration = gson.fromJson(configurationString, Configuration.class);
        return new Main(configuration);
    }

    public static void main(String[] args) {
        if (args.length != 1) {
            logger.error("Invalid arguments. Pass path to configuration as first argument.");
            return;
        }
        Main main = createFromConfigurationFile(new File(args[0]));
        main.run();
    }

    @Override
    public void run() {
        logger.info(configuration.command.name());
        switch (configuration.command) {
            case ProbeAddressesCPU:
                CPUProber prober = new CPUProber(configuration.probeAddressesCPU);
                prober.run();
                break;
            case ExtractAddresses:
                AddressesExtractor addressesExtractor = new AddressesExtractor(configuration.extractAddresses);
                addressesExtractor.run();
                break;
            case ProbeAddressesOpenCL:
                OpenCLProber openCLProber = new OpenCLProber(configuration.probeAddressesOpenCl);
                openCLProber.run();
                break;
            case AddressFilesToLMDB:
                AddressFilesToLMDB addressFilesToLMDB = new AddressFilesToLMDB(configuration.addressFilesToLMDB);
                addressFilesToLMDB.run();
                break;
            default:
                throw new UnsupportedOperationException(Command.ProbeAddressesOpenCL.toString() + " currently not supported." );
        }
    }
}
