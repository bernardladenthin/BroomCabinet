package net.ladenthin.screenshot.byteprotocol;

import net.ladenthin.screenshot.Chunk;
import net.ladenthin.screenshot.State;

import java.io.*;
import java.util.ArrayList;
import java.util.Collection;

public class Message {

    public final static int COMMAND_REQUEST_STATE = 1;
    public final static int COMMAND_REQUEST_CHUNKS = 2;
    public final static int COMMAND_RESPONSE_STATE = 4;
    public final static int COMMAND_RESPONSE_CHUNKS = 8;
    public final static int COMMAND_INVALID_REQUEST = 16;

    private int command;

    private Collection<Long> requestChunkIds;
    private State responseStateContainer;
    private Collection<Chunk> responseChunks;

    public void deserialize(byte[] encoded) throws IOException {
        DataInputStream dis = new DataInputStream(new ByteArrayInputStream(encoded));

        command = dis.readInt();

        if (isResponseState()) {
            responseStateContainer = new State();
            responseStateContainer.setTimestamp(dis.readLong());
            Chunk[][] chunks = new Chunk[dis.readInt()][dis.readInt()];
            for (int i = 0; i < chunks.length; i++) {
                for (int j = 0; j < chunks[i].length; j++) {
                    Chunk chunk = new Chunk();
                    chunk.setId(dis.readLong());
                    chunks[i][j] = chunk;
                }
            }
            responseStateContainer.setChunks(chunks);
        }

        if (isRequestChunks()) {
            int size = dis.readInt();
            requestChunkIds = new ArrayList<>(size);
            for (int i = 0; i < size; i++) {
                requestChunkIds.add(dis.readLong());
            }
        }

        if (isResponseChunks()) {
            int size = dis.readInt();
            responseChunks = new ArrayList<>(size);
            for (int i = 0; i < size; i++) {
                Chunk chunk = new Chunk();
                chunk.setId(dis.readLong());
                chunk.setWidth(dis.readInt());
                chunk.setHeight(dis.readInt());
                byte[] compressedThreeByteBGR = new byte[dis.readInt()];
                int read = dis.read(compressedThreeByteBGR);
                if (read != compressedThreeByteBGR.length) {
                    throw new IOException("Could not read compressedThreeByteBGR.");
                }
                chunk.setCompressedThreeByteBGR(compressedThreeByteBGR);
                responseChunks.add(chunk);
            }
        }
    }

    public byte[] serialize() throws IOException {
        ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
        BufferedOutputStream bufferedOutputStream = new BufferedOutputStream(byteArrayOutputStream);
        DataOutputStream dataOutputStream = new DataOutputStream(bufferedOutputStream);

        dataOutputStream.writeInt(command);

        if (isResponseState()) {
            dataOutputStream.writeLong(responseStateContainer.getTimestamp());
            Chunk[][] chunks = responseStateContainer.getChunks();
            dataOutputStream.writeInt(chunks.length);
            dataOutputStream.writeInt(chunks[0].length);
            for (int i = 0; i < chunks.length; i++) {
                for (int j = 0; j < chunks[i].length; j++) {
                    Chunk chunk = chunks[i][j];
                    dataOutputStream.writeLong(chunk.getId());
                }
            }
        }

        if (isRequestChunks()) {
            if (requestChunkIds == null) {
                dataOutputStream.writeInt(0);
            } else {
                dataOutputStream.writeInt(requestChunkIds.size());
                for (Long requestChunkId : requestChunkIds) {
                    dataOutputStream.writeLong(requestChunkId);
                }
            }
        }

        if (isResponseChunks()) {
            if (responseChunks == null) {
                dataOutputStream.writeInt(0);
            } else {
                dataOutputStream.writeInt(responseChunks.size());
                for (Chunk chunk : responseChunks) {
                    dataOutputStream.writeLong(chunk.getId());
                    dataOutputStream.writeInt(chunk.getWidth());
                    dataOutputStream.writeInt(chunk.getHeight());
                    dataOutputStream.writeInt(chunk.getCompressedThreeByteBGR().length);
                    dataOutputStream.write(chunk.getCompressedThreeByteBGR());
                }
            }
        }

        dataOutputStream.flush();
        return byteArrayOutputStream.toByteArray();
    }

    public boolean isRequestState() {
        return (command & COMMAND_REQUEST_STATE) == COMMAND_REQUEST_STATE;
    }

    public void setRequestState(boolean value) {
        if (value) {
            command |= COMMAND_REQUEST_STATE;
        } else {
            command &= ~COMMAND_REQUEST_STATE;
        }
    }

    public boolean isRequestChunks() {
        return (command & COMMAND_REQUEST_CHUNKS) == COMMAND_REQUEST_CHUNKS;
    }

    public void setRequestChunks(boolean value) {
        if (value) {
            command |= COMMAND_REQUEST_CHUNKS;
        } else {
            command &= ~COMMAND_REQUEST_CHUNKS;
        }
    }

    public boolean isResponseState() {
        return (command & COMMAND_RESPONSE_STATE) == COMMAND_RESPONSE_STATE;
    }

    public void setResponseState(boolean value) {
        if (value) {
            command |= COMMAND_RESPONSE_STATE;
        } else {
            command &= ~COMMAND_RESPONSE_STATE;
        }
    }

    public boolean isResponseChunks() {
        return (command & COMMAND_RESPONSE_CHUNKS) == COMMAND_RESPONSE_CHUNKS;
    }

    public void setResponseChunks(boolean value) {
        if (value) {
            command |= COMMAND_RESPONSE_CHUNKS;
        } else {
            command &= ~COMMAND_RESPONSE_CHUNKS;
        }
    }

    public boolean isInvalidRequest() {
        return (command & COMMAND_INVALID_REQUEST) == COMMAND_INVALID_REQUEST;
    }

    public void setInvalidRequest(boolean value) {
        if (value) {
            command |= COMMAND_INVALID_REQUEST;
        } else {
            command &= ~COMMAND_INVALID_REQUEST;
        }
    }

    public void setResponseChunks(Collection<Chunk> chunks) {
        this.responseChunks = chunks;
    }

    public Collection<Chunk> getResponseChunks() {
        return responseChunks;
    }

    public Collection<Long> getRequestChunkIds() {
        return requestChunkIds;
    }

    public void setRequestChunkIds(Collection<Long> requestChunkIds) {
        this.requestChunkIds = requestChunkIds;
    }

    @Override
    public String toString() {
        return "Message{" +
                "command=" + command +
                ", requestChunkIds=" + requestChunkIds +
                ", responseStateContainer=" + responseStateContainer +
                ", responseChunks=" + responseChunks +
                '}';
    }

    public State getResponseStateContainer() {
        return responseStateContainer;
    }

    public void setResponseStateContainer(State responseStateContainer) {
        this.responseStateContainer = responseStateContainer;
    }
}