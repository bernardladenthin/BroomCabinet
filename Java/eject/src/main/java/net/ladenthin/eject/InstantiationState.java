// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.eject;

import java.util.EnumSet;
import java.util.Set;

/**
 * Instantiation state machine.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public enum InstantiationState {
    Initialized {
        @Override
        public Set<InstantiationState> possibleNext() {
            return EnumSet.of(ErrorReadingFile, ReadFileSuccessful);
        }
    },

    ErrorReadingFile {
        @Override
        public Set<InstantiationState> possibleNext() {
            return EnumSet.of(DefaultConstructorSuccessful, ErrorUsingDefaultConstructor,
                    NoDefaultConstructor);
        }
    },
    NoDefaultConstructor,
    DefaultConstructorSuccessful,
    ErrorUsingDefaultConstructor,
    ReadFileSuccessful;

    public Set<InstantiationState> possibleNext() {
        return EnumSet.noneOf(InstantiationState.class);
    }

    public InstantiationState transition(InstantiationState nextState) {
        if (this.possibleNext().contains(nextState)) {
            return nextState;
        } else {
            throw new IllegalStateException();
        }
    }

}
