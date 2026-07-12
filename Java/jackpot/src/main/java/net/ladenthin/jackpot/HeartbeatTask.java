// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot;

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
