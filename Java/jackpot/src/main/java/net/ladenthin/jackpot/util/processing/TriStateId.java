// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util.processing;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

@Deprecated
public class TriStateId {

    /**
     * Hold the ID.
     */
    private final AtomicLong id = new AtomicLong();

    /**
     * Indicates an initialized {@link id}.
     */
    private final AtomicBoolean isSet = new AtomicBoolean(false);

    public synchronized boolean isSet() {
        return isSet.get();
    }

    public synchronized void initialize(long id) {
        this.id.set(id);
        isSet.set(true);
    }

    public synchronized long incrementAndGet() {
        return id.incrementAndGet();
    }

    public synchronized long initializeOrIncrementAndGet(long id) {
        if (isSet()) {
            return incrementAndGet();
        } else {
            initialize(id);
            return id;
        }
    }

    public synchronized void unset() {
        isSet.set(false);
    }

    public synchronized long getLastId() {
        return id.get();
    }
}
