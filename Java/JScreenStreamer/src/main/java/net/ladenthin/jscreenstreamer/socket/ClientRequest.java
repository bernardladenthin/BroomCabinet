// SPDX-FileCopyrightText: 2017 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jscreenstreamer.socket;

public interface ClientRequest {
    byte[] call(byte[] request);
}
