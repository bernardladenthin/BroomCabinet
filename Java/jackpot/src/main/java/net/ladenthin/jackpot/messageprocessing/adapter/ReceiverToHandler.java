// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing.adapter;

import net.ladenthin.jackpot.messageprocessing.ParallelMessageTransmitter;
import net.ladenthin.jackpot.messageprocessing.ParallelMessageReceiver;

@Deprecated
public class ReceiverToHandler<T> implements ParallelMessageReceiver<T> {

    private ParallelMessageTransmitter<T> parallelMessageHandler;

    public ReceiverToHandler(ParallelMessageTransmitter<T> parallelMessageHandler) {
        this.parallelMessageHandler = parallelMessageHandler;
    }

    @Override
    public void receiveMessage(T tm) {
        parallelMessageHandler.transmitMessage(tm);
    }
}
