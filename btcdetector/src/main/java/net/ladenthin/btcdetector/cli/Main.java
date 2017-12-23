package net.ladenthin.btcdetector.cli;

import com.google.gson.Gson;
import net.ladenthin.btcdetector.*;
import net.ladenthin.btcdetector.configuration.Command;
import net.ladenthin.btcdetector.configuration.Configuration;
import net.ladenthin.btcdetector.configuration.ProbeAddresses;
import net.ladenthin.javacommons.StreamHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;

// VM option: -Dorg.slf4j.simpleLogger.defaultLogLevel=trace
public class Main implements Runnable {

    private final static Logger logger = LoggerFactory.getLogger(Main.class);

    private final File configFile;

    public Main(File configFile) {
        this.configFile = configFile;
    }

    public static void main(String[] args) {
        if (args.length != 1) {
            logger.error("Invalid arguments. Pass path to configuration as first argument.");
            return;
        }
        new Main(new File(args[0])).run();
    }

    @Override
    public void run() {
        try {
            Gson gson = new Gson();
            String configurationString = new StreamHelper().readFullyAsUTF8String(configFile);
            logger.info("Check configuration");
            Configuration configuration = gson.fromJson(configurationString, Configuration.class);
            logger.info(configuration.command.name());
            switch (configuration.command) {
                case ProbeAddressesCPU:
                    CPUProber prober = new CPUProber(configuration.probeAddressesCPU);
                    prober.run();
                    break;
                case ProbeAddressesOpenCL:
                    OpenCLProber openCLProber = new OpenCLProber();
                    openCLProber.run();
                    break;
                case BlockchainAnalysis:
                    Analyser analyser = new Analyser(configuration.blockchainAnalysis);
                    analyser.run();
                    break;
                case ExtractAddresses:
                    AddressesExtractor addressesExtractor = new AddressesExtractor(configuration.extractAddresses);
                    addressesExtractor.run();
                    break;
            }
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}
