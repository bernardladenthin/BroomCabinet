// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.messageprocessing.adapter;

import net.ladenthin.jackpot.messageprocessing.ParallelMessageTransmitter;
import net.ladenthin.jackpot.messageprocessing.ParallelMessageReceiver;

@Deprecated
public class TransmitterToInformant<T> implements ParallelMessageTransmitter<T> {

    private ParallelMessageReceiver<T> parallelMessageInformant;

    public TransmitterToInformant(ParallelMessageReceiver<T> parallelMessageInformant) {
        this.parallelMessageInformant = parallelMessageInformant;
    }

    @Override
    public void transmitMessage(T tm) {
        parallelMessageInformant.receiveMessage(tm);
    }
}
