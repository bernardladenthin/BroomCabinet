package de.fraunhofer.fokus.jackpot;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public final class CurrentWritingLock {

    private final ErrorLayer errorLayer;

    private final AtomicBoolean currentWriting = new AtomicBoolean(false);

    private final AtomicLong currentWritingId = new AtomicLong();

    public CurrentWritingLock(final ErrorLayer errorLayer) {
        this.errorLayer = errorLayer;
    }

    /**
     * This block is extremely rare. It only occurs if the run method hangs to long at the position
     * sendButNotRegistred and the deleteId or resendId was called before finished. We must ensure
     * the id and the message was put to the written NavigableMap. It should never be happen but
     * this way is better as blocking the written map during the sending progress.
     * This method should not be synchronized!
     * 
     * @param id
     */
    public final void blockUntilCurrentWriting(long id) {
        for (;;) {
            final boolean block;
            final long blockId;
            synchronized (this) {
                block = currentWriting.get();
                blockId = currentWritingId.get();
            }
            if (block && blockId == id) {
                try {
                    Thread.sleep(10);
                } catch (InterruptedException e) {
                    errorLayer.notifyException(e);
                }
            } else {
                return;
            }
        }
    }

    public final synchronized void setLock(final long id) {
        currentWriting.set(true);
        currentWritingId.set(id);
    }

    public final synchronized void releaseLock() {
        currentWriting.set(false);
    }
}
