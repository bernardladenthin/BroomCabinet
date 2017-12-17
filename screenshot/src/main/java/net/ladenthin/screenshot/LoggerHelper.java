package net.ladenthin.screenshot;

import java.util.logging.Level;
import java.util.logging.Logger;

public class LoggerHelper {
    public static void seRootLoggerLevel(Level level) {
        Logger rootLog = Logger.getLogger("");
        rootLog.setLevel( Level.FINE );
        rootLog.getHandlers()[0].setLevel( Level.FINE );
        /*
        Handler[] handlers = root.getHandlers();
        for(Handler h: handlers){
            h.setLevel(level);
        }
        */
    }
}