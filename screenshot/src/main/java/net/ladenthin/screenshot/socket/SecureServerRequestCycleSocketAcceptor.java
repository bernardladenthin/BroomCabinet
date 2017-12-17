package net.ladenthin.screenshot.socket;

import java.net.ServerSocket;
import java.net.Socket;

public class SecureServerRequestCycleSocketAcceptor implements Runnable {

	private final int port;
	private final ClientRequest clientRequest;
	private final byte[] key;

	public SecureServerRequestCycleSocketAcceptor(int port, byte[] key, ClientRequest clientRequest) {
		this.port = port;
		this.key = key;
		this.clientRequest = clientRequest;
	}

	@Override
	public void run() {
		try {
			ServerSocket serverSocket = new ServerSocket(port);
			for (;;) {
				Socket clientSocket = serverSocket.accept();
                SecureServerRequestCycleSocket secureServerRequestCycleSocket = new SecureServerRequestCycleSocket(clientSocket, key, clientRequest);
                new Thread(secureServerRequestCycleSocket).start();
			}
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
}
