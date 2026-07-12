package de.fraunhofer.fokus.jackpot.messageprocessing.adapter;

import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageTransmitter;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageReceiver;

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
