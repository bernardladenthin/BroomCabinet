/**
 * Copyright 2014 Fraunhofer FOKUS
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
package de.fraunhofer.fokus.eject;

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
