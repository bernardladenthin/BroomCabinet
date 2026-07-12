// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jackpot.interfaces;

import net.ladenthin.jackpot.messageprocessing.SequentialBinaryMessageTransmitter;

public interface WriteManagement extends SequentialBinaryMessageTransmitter {

    void resendId(long id);

    void deleteId(long id);
}
