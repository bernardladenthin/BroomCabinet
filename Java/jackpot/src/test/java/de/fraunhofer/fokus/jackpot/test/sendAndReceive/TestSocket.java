package de.fraunhofer.fokus.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import de.fraunhofer.fokus.jackpot.configuration.*;

public class TestSocket extends TestConnector {

    private final static String host = "localhost";
    private final static int port = 12345;

    @Override
    CTransceiverSession getServerTransceiver() {
        CServerSocketConnector cServerSocketConnector = new CServerSocketConnector(port);
        CConnector serverConnector = new CConnector(cServerSocketConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.ServerSocketConnection, serverConnector);

        return new CTransceiverSession(
            "serverTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

    @Override
    CTransceiverSession getClientTransceiver() {
        CClientSocketConnector cClientSocketConnector = new CClientSocketConnector(host, port);
        CConnector clientConnector = new CConnector(cClientSocketConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.ClientSocketConnection, clientConnector);

        return new CTransceiverSession(
            "clientTransceiver",
            new TypeToken<SimpleMessage>(){}.getType(),
            SimpleMessage.class,
            transceiverConfiguration
        );
    }

}
