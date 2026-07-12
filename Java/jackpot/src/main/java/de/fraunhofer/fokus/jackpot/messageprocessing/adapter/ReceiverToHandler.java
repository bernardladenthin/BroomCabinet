package de.fraunhofer.fokus.jackpot.messageprocessing.adapter;

import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageTransmitter;
import de.fraunhofer.fokus.jackpot.messageprocessing.ParallelMessageReceiver;

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
