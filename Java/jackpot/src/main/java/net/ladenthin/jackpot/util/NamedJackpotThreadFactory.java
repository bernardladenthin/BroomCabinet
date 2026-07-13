// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.util;

import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicLong;

/**
 * A {@link ThreadFactory} that names its threads with a jackpot-specific prefix, so all
 * threads created by this library are identifiable (e.g. in thread dumps and in the
 * shutdown-termination test).
 */
public final class NamedJackpotThreadFactory implements ThreadFactory {

    private final String namePrefix;

    private final AtomicLong threadNumber = new AtomicLong();

    /**
     * @param namePrefix the prefix for every created thread name; a running number is appended
     */
    public NamedJackpotThreadFactory(final String namePrefix) {
        this.namePrefix = namePrefix;
    }

    @Override
    public Thread newThread(Runnable r) {
        return new Thread(r, namePrefix + "-" + threadNumber.incrementAndGet());
    }
}
