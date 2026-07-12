// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.eject;

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
