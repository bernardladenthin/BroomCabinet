package de.fraunhofer.fokus.jackpot.test.sendAndReceive;

import com.google.gson.reflect.TypeToken;
import de.fraunhofer.fokus.jackpot.configuration.*;
import org.junit.Ignore;

@Ignore
public class TestWindowsPipe extends TestConnector {

    @Override
    final CTransceiverSession getServerTransceiver() {
        CWindowsNamedPipeServerConnector cWindowsNamedPipeServerConnector = new CWindowsNamedPipeServerConnector("testpipe");
        CConnector serverConnector = new CConnector(cWindowsNamedPipeServerConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.WindowsNamedPipeServer, serverConnector);

        return new CTransceiverSession(
                "serverTransceiver",
                new TypeToken<SimpleMessage>(){}.getType(),
                SimpleMessage.class,
                transceiverConfiguration
        );
    }

    @Override
    final CTransceiverSession getClientTransceiver() {
        CWindowsNamedPipeClientConnector cWindowsNamedPipeClientConnector = new CWindowsNamedPipeClientConnector("testpipe");
        CConnector clientConnector = new CConnector(cWindowsNamedPipeClientConnector);
        CTransceiver transceiverConfiguration = new CTransceiver(ConnectionType.WindowsNamedPipeClient, clientConnector);

        return new CTransceiverSession(
                "clientTransceiver",
                new TypeToken<SimpleMessage>(){}.getType(),
                SimpleMessage.class,
                transceiverConfiguration
        );
    }

}
