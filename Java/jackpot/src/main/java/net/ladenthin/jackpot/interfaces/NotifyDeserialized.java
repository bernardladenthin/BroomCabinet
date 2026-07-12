// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.interfaces;

public interface NotifyDeserialized {

    /**
     * Notify a deserialized Message is available in the next moment.
     */
    void notifyDeserialized();
}
