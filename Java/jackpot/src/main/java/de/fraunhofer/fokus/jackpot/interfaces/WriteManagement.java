package de.fraunhofer.fokus.jackpot.interfaces;

import de.fraunhofer.fokus.jackpot.messageprocessing.SequentialBinaryMessageTransmitter;

public interface WriteManagement extends SequentialBinaryMessageTransmitter {

    void resendId(long id);

    void deleteId(long id);
}
