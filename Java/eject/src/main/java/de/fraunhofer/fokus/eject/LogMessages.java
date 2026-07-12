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

/**
 * Constant log messages.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public enum LogMessages {
    NEWLINE {
        public String toString() {
            return "\n";
        }
    },
    ERROR {
        public String toString() {
            return "Could not read or instantiate the object.";
        }
    },
    FILE_FOUND {
        public String toString() {
            return "File found, read successfully.";
        }
    },
    FILE_NOT_EXIST {
        public String toString() {
            return "The file does not exist: ";
        }
    },
    FILE_CAN_NOT_READ {
        public String toString() {
            return "File can not be read.";
        }
    },
    DIFFER {
        public String toString() {
            return "The following object was created " + "(This is the created, internal JSON "
                    + "data object and might differ from the " + "initial JSON-String read).";
        }
    },
    TRY_DEFAULT_CONSTRUCTOR {
        public String toString() {
            return "Try to instantiate using the default constructor.";
        }
    },
    DEFAULT_CONSTRUCTOR_USED {
        public String toString() {
            return "Object instantiated using the default constructor.";
        }
    },
    CLASS_TO_INSTANTIATE {
        public String toString() {
            return "Class to instantiate: ";
        }
    },
    NORMAL_STRING {
        public String toString() {
            return "The normal string representation.";
        }
    },
    PRETTY_STRING {
        public String toString() {
            return "The pretty string representation.";
        }
    }
}
