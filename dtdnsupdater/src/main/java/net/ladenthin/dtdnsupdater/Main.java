package net.ladenthin.dtdnsupdater;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Logger;

public class Main {

    public class ServiceTask implements Runnable {
        public void run() {
            if (nextUpdate > System.currentTimeMillis()) {
                // skip this wakeup
                return;
            }

            List<String> lines;
            try {
                lines = getLinesFromUrl(updateUrlS);
            } catch (IOException e) {
                logger.warning("Error during update, try again in a few moments. " + e.getMessage());
                // try again in one minute
                nextUpdate = System.currentTimeMillis() + TimeUnit.MINUTES.toMillis(1);
                return;
            }
            // send an update again in 20 minutes
            nextUpdate = System.currentTimeMillis() + TimeUnit.MINUTES.toMillis(20);
            logger.info("Successfull updated. " + lines.toString());
        }
    }

    private final static String updateUrlS = "http://www.dtdns.com/api/autodns.cfm?id=example.dtdns.net&pw=example";

    private final static Logger logger = Logger.getLogger(Main.class.getSimpleName());

    private volatile long nextUpdate = -1;

    public static void main(String[] argv) {
        Main main = new Main();
        main.run();
    }

    private void run() {
        ServiceTask st = new ServiceTask();
        ScheduledExecutorService executor = Executors.newScheduledThreadPool(1);
        executor.scheduleAtFixedRate(st, 0, 1, TimeUnit.SECONDS);
    }

    private static List<String> getLinesFromUrl(String sUrl) throws IOException {
        URL url = new URL(sUrl);
        InputStream is = url.openConnection().getInputStream();

        BufferedReader reader = new BufferedReader(new InputStreamReader(is));

        String line;
        List<String> lines = new ArrayList<>();
        while ((line = reader.readLine()) != null) {
            lines.add(line);
        }

        reader.close();
        return lines;
    }
}