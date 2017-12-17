package net.ladenthin.screenshot;

import java.awt.image.BufferedImage;
import java.io.IOException;
import java.sql.SQLException;
import java.util.List;
import java.util.zip.DataFormatException;

public interface ImagePersistence {
    void initConnection() throws ClassNotFoundException, SQLException;
    void initPersistence() throws SQLException;
    State persistChunks(Chunk[][] chunks) throws SQLException, IOException;

    Chunk getChunkById(long id) throws SQLException;

    void insertChunk(Chunk chunk) throws SQLException;

    void insertState(State state) throws SQLException;

    List<State> getLastStates(int limit) throws SQLException, IOException, DataFormatException;

    /**
     * DESCENDING Order.
     */
    List<State> getDrawableStates(List<State> states, int limit) throws SQLException;

    /**
     * DESCENDING Order.
     */
    List<State> getAllDrawableStates(int limit) throws SQLException, IOException, DataFormatException;

    BufferedImage getLastDrawableState() throws SQLException, IOException, DataFormatException;
}