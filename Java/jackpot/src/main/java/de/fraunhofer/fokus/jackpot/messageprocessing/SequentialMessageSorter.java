/**
 * Copyright 2013 Fraunhofer FOKUS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
package de.fraunhofer.fokus.jackpot.messageprocessing;

import java.util.HashMap;
import java.util.Map;

import de.fraunhofer.fokus.jackpot.configuration.CMessageIdLong;

/**
 * Generic message sorter to pass-through messages in their natural order.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
@Deprecated
public class SequentialMessageSorter<T> implements ParallelMessageTransmitter<T> {

    /**
     * The last message ID.
     */
    private long lastMessageId;

    /**
     * Map to store messages that are not in order.
     */
    private final Map<Long, T> messageMap = new HashMap<>();

    /**
     * The messageHandler.
     */
    private final SequentialMessageReceiver<T> sequentialMessageReceiver;

    @SuppressWarnings("unused")
    private final CMessageIdLong messageIdLong;

    /**
     * Construct the sorter.
     *
     * @param sequentialMessageReceiver
     * sequentialMessageReceiver that receives the messages in their order.
     */
    public SequentialMessageSorter(final SequentialMessageReceiver<T> sequentialMessageReceiver,
        final CMessageIdLong messageIdLong) {
        this.sequentialMessageReceiver = sequentialMessageReceiver;
        this.messageIdLong = messageIdLong;
        lastMessageId = messageIdLong.begin;
    }

    /**
     * Get the expected message ID.
     *
     * @return The Expected message ID. Unitless.
     */
    private long getExpectedMessageId() {
        return lastMessageId + 1;
    }

    /**
     * Get for the {@link #sequentialMessageReceiver} reference.
     *
     * @return The {@link #sequentialMessageReceiver} reference.
     */
    public SequentialMessageReceiver<T> getSequentialMessageReceiver() {
        return sequentialMessageReceiver;
    }

    public long getLastMessageId() {
        return lastMessageId;
    }

    /**
     * Set the @link {@link #lastMessageId}. <b>Warning: This function is dangerous.</b> <b>Please
     * use this function only if you know what you are doing.</b>
     *
     * @param lastMessageId
     */
    public void setLastMessageId(final long lastMessageId) {
        this.lastMessageId = lastMessageId;
    }

    /**
     * Set the @link {@link #messageMap}. <b>Warning: This function is dangerous.</b> <b>Please use
     * this function only if you know what you are doing.</b>
     */
    public void clearMessageMap() {
        this.messageMap.clear();
    }

    /**
     * Update the {@link #lastMessageId}.
     */
    private void updateLastMessageId() {
        lastMessageId = getExpectedMessageId();
    }

    /**
     * Process the message and update the {@link #lastMessageId}.
     *
     * @param tm
     * The message to process.
     */
    @SuppressWarnings("unused")
    private void processMessage(final T tm) {
        updateLastMessageId();
        throw new RuntimeException("do not use this");
        // sequentialMessageReceiver.transmitMessage(tm);
    }

    @Override
    public void transmitMessage(T msg) {
        // see below
        throw new RuntimeException("do not use this");
    }

    /*
    @Override
    public synchronized void transmitMessage(final T tm) {
        if(tm.information.messageIdLong == getExpectedMessageId()) {
            processMessage(tm);
        } else {
            assert (
                !messageMap.containsKey(tm.information.messageIdLong)
            ) : "messageMap already containsKey";

            if(tm.information.messageIdLong < getExpectedMessageId()) {
                throw new RuntimeException("message ID lower than expected message ID");
            }

            messageMap.put(tm.information.messageIdLong, tm);
        }

        while(messageMap.containsKey(getExpectedMessageId())) {
            final TMessage<T> storedTm = messageMap.get(getExpectedMessageId());
            messageMap.remove(getExpectedMessageId());
            processMessage(storedTm);
        }
    }
    */

}
