package net.ladenthin.screenshot.socket;

public interface ClientRequest {
    byte[] call(byte[] request);
}
