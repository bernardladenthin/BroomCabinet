package de.fraunhofer.fokus.jackpot;

import java.util.TimerTask;

/**
 * Created by bernard on 25.04.14.
 */
public class HeartbeatTask extends TimerTask {

    private final WriteLayer writeLayer;

    public HeartbeatTask(WriteLayer writeLayer) {
        this.writeLayer = writeLayer;
    }

    @Override
    public void run() {
        writeLayer.heartbeatSignal();
    }
}
