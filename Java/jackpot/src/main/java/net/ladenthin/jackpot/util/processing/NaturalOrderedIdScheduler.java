// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util.processing;

import java.util.Map.Entry;
import java.util.NavigableMap;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicLong;

@Deprecated
public class NaturalOrderedIdScheduler<T> implements ParallelIdHandler<T> {

    /**
     * Always contain the next ID.
     */
    private final AtomicLong expectedId;

    private final TriStateId idDistribution = new TriStateId();

    private final long initialId;

    private final NavigableMap<Long, T> processMap = new TreeMap<>();

    private final SequentialIdHandler<T> handler;

    public synchronized long getNextId() {
        return idDistribution.initializeOrIncrementAndGet(initialId);
    }

    public synchronized void reset() {
        expectedId.set(initialId);
        processMap.clear();
    }

    public synchronized boolean safeReset() {
        if (isEmpty() && idDistribution.isSet()) {
            if (expectedId.get() == idDistribution.getLastId()) {

            }
            expectedId.set(initialId);
            idDistribution.initialize(initialId);
            return true;
        }
        return false;
    }

    public synchronized boolean isEmpty() {
        return processMap.size() > 0 ? false : true;
    }

    NaturalOrderedIdScheduler(SequentialIdHandler<T> processor, final long initialId) {
        this.handler = processor;
        this.initialId = initialId;
        this.expectedId = new AtomicLong(this.initialId);
    }

    /**
     * Process the message and update the {@link #lastMessageId}.
     * 
     * @param tm
     * The message to process.
     */
    private void toProcessor(final long id, final T t) {
        expectedId.incrementAndGet();
        handler.process(id, t);
    }

    @Override
    public synchronized void process(final long id, final T t) {
        if (id == expectedId.get()) {
            toProcessor(id, t);
        } else {
            assert (!processMap.containsKey(id)) : "processMap already containsKey";

            if (id < expectedId.get()) {
                throw new RuntimeException("id < nextId");
            }
            processMap.put(id, t);
        }

        while (processMap.firstKey() == expectedId.get()) {
            final Entry<Long, T> entry = processMap.pollFirstEntry();
            toProcessor(entry.getKey(), entry.getValue());
        }
    }

}
