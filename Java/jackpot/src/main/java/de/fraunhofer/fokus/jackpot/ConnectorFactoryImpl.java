package de.fraunhofer.fokus.jackpot;

import de.fraunhofer.fokus.jackpot.configuration.CTransceiverSession;
import de.fraunhofer.fokus.jackpot.connector.*;

public class ConnectorFactoryImpl implements ConnectorFactory {

    private final CTransceiverSession cTransceiverSession;

    public ConnectorFactoryImpl(CTransceiverSession cTransceiverSession) {
        this.cTransceiverSession = cTransceiverSession;
    }

    @Override
    public Connector getConnector() {
        switch (cTransceiverSession.transceiverConfiguration.connectionType) {
            case ServerSocketConnection:
                return new ServerSocketConnector(
                        cTransceiverSession.transceiverConfiguration.connector.serverSocketConnector
                );
            case ClientSocketConnection:
                return new ClientSocketConnector(
                        cTransceiverSession.transceiverConfiguration.connector.clientSocketConnector
                );
            case UnixNamedPipeServer:
                return new UnixNamedPipeServerConnector(
                        cTransceiverSession.transceiverConfiguration.connector.unixNamedPipeServer
                );
            case UnixNamedPipeClient:
                return new UnixNamedPipeClientConnector(
                        cTransceiverSession.transceiverConfiguration.connector.unixNamedPipeClient
                );
            case WindowsNamedPipeServer:
                return new WindowsNamedPipeServerConnector(
                        cTransceiverSession.transceiverConfiguration.connector.windowsNamedPipeServer
                );
            case WindowsNamedPipeClient:
                return new WindowsNamedPipeClientConnector(
                        cTransceiverSession.transceiverConfiguration.connector.windowsNamedPipeClient
                );
            default:
                throw new RuntimeException("Unknown connector.");
        }
    }

}
