package net.ladenthin.jscreenstreamer.socket;

public interface ClientRequest {
    byte[] call(byte[] request);
}
