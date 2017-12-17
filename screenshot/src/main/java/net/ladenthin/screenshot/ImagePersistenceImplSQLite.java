package net.ladenthin.screenshot;

import java.awt.image.BufferedImage;
import java.io.*;
import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.zip.DataFormatException;

public class ImagePersistenceImplSQLite implements ImagePersistence {

    private static final Logger logger = Logger.getLogger(ImagePersistenceImplSQLite.class.getName());

    private static final long FIRST_CHUNK_ID = 1;
    private static final long FIRST_STATE_ID = 1;
    Connection c;
    private static final String DB_DRIVER = "org.sqlite.JDBC";
    private final String dbConnection;

    private long nextChunkId;
    private long nextStateId;

    public ImagePersistenceImplSQLite(String database) {
        dbConnection = "jdbc:sqlite:" + database;
    }

    public void initConnection() throws ClassNotFoundException, SQLException {
        Class.forName(DB_DRIVER);
        c = DriverManager.getConnection(dbConnection);
    }

    public void initPersistence() throws SQLException {
        createTableImages();
        createTableStates();
        initNextChunkId();
        initNextStateId();
    }

    private void initNextChunkId() throws SQLException {
        String sql = "SELECT id from images ORDER BY id DESC LIMIT 1";
        Statement statement = c.createStatement();
        ResultSet rs = statement.executeQuery(sql);

        if (!rs.next()) {
            nextChunkId = FIRST_CHUNK_ID;
            logger.info("no initial chunk id found, set to: " + nextChunkId);
            statement.close();
            return;
        }

        nextChunkId = rs.getLong("id");
        nextChunkId++;
        logger.info("initial chunk id found, set to: " + nextChunkId);

        statement.close();
    }

    private void initNextStateId() throws SQLException {
        String sql = "SELECT id from states ORDER BY id DESC LIMIT 1";
        Statement statement = c.createStatement();
        ResultSet rs = statement.executeQuery(sql);

        if (!rs.next()) {
            nextStateId = FIRST_STATE_ID;
            logger.info("no initial state id found, set to: " + nextStateId);
            statement.close();
            return;
        }

        nextStateId = rs.getLong("id");
        nextStateId++;
        logger.info("initial id state found, set to: " + nextStateId);

        statement.close();
    }


    @Override
    public State persistChunks(Chunk[][] chunks) throws SQLException, IOException {
        int foundPersisted = 0;
        int foundNew = 0;
        State state = new State();
        int iterCount = 0;
        for (int row = 0; row < chunks.length; row++) {
            for (int col = 0; col < chunks[row].length; col++) {
                iterCount++;
                Chunk chunk = chunks[row][col];

                logger.finest("digest: " + chunk.getDigest());
                Long idByDigest = getChunkIdByDigest(chunk.getDigest());
                // is the chunk in the database
                if (idByDigest != null) {
                    chunk.setId(idByDigest);
                    logger.finest("Find chunk.");
                    foundPersisted++;
                    //Chunk chunksFromDigest = getChunkByDigest(chunk.getDigest());
                } else {
                    logger.finest("Could not find chunk.");
                    chunk.setId(nextChunkId++);
                    insertChunk(chunk);
                    foundNew++;
                }

                if (logger.isLoggable(Level.FINEST)) {
                    logger.finest(chunk.getMetrics());
                }
            }
        }
        state.setChunks(chunks);
        state.setTimestamp(System.currentTimeMillis());
        insertState(state);
        logger.finest("iterCount: " + iterCount);
        logger.finest("foundPersisted: " + foundPersisted);
        logger.finest("foundNew: " + foundNew);
        logger.finest("nextChunkId: " + nextChunkId);
        return state;
    }

    @Override
    public Chunk getChunkById(long id) throws SQLException {
        String sql = "SELECT CompressedThreeByteBGR, width, height FROM images WHERE id=?";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setLong(1, id);
        ResultSet rs = statement.executeQuery();

        Chunk chunk = new Chunk();
        if (!rs.next()) {
            statement.close();
            return null;
        }

        chunk.setId(id);
        chunk.setWidth(rs.getInt("width"));
        chunk.setHeight(rs.getInt("height"));
        chunk.setCompressedThreeByteBGR(rs.getBytes("CompressedThreeByteBGR"));
        statement.close();
        return chunk;
    }

    private Chunk getChunkByDigest(String digest) throws SQLException, IOException {
        String sql = "SELECT id, CompressedThreeByteBGR, width, height FROM images WHERE digest=?";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setString(1, digest);
        ResultSet rs = statement.executeQuery();

        Chunk chunk = new Chunk();
        if (!rs.next()) {
            statement.close();
            return null;
        }

        chunk.setDigest(digest);
        chunk.setId(rs.getLong("id"));
        chunk.setCompressedThreeByteBGR(rs.getBytes("CompressedThreeByteBGR"));
        chunk.setWidth(rs.getInt("width"));
        chunk.setHeight(rs.getInt("height"));
        statement.close();
        return chunk;
    }

    private Long getChunkIdByDigest(String digest) throws SQLException, IOException {
        String sql = "SELECT id FROM images WHERE digest=?";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setString(1, digest);
        ResultSet rs = statement.executeQuery();

        if (!rs.next()) {
            statement.close();
            return null;
        }

        return rs.getLong("id");
    }

    private void createTableImages() throws SQLException {
        String sql = "CREATE TABLE if not exists images (" +
                "id INTEGER NOT NULL," +
                "digest blob," +
                "CompressedThreeByteBGR blob," +
                "width INTEGER NOT NULL," +
                "height INTEGER NOT NULL," +
                "PRIMARY KEY(id)" +
                ");";
        Statement statement = c.createStatement();
        statement.executeUpdate(sql);
        statement.close();
    }

    private void createTableStates() throws SQLException {
        String sql = "CREATE TABLE if not exists states (" +
                "id INTEGER NOT NULL," +
                "ltimestamp INTEGER NOT NULL," +
                "chunkids BLOB NOT NULL," +
                "PRIMARY KEY(id)" +
                ");";
        Statement statement = c.createStatement();
        statement.executeUpdate(sql);
        statement.close();
    }

    @Override
    public void insertChunk(Chunk chunk) throws SQLException {
        String sql = "INSERT INTO 'images'"
                + "('id', 'digest', 'CompressedThreeByteBGR', 'width', 'height') VALUES (?,?,?,?,?)";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setLong(1, chunk.getId());
        statement.setString(2, chunk.getDigest());
        statement.setBytes(3, chunk.getCompressedThreeByteBGR());
        statement.setInt(4, chunk.getWidth());
        statement.setInt(5, chunk.getHeight());
        statement.executeUpdate();
        statement.close();
    }

    @Override
    public void insertState(State state) throws SQLException {
        String sql = "INSERT INTO 'states'"
                + "('id', 'ltimestamp', 'chunkids') VALUES (?,?,?)";
        PreparedStatement statement = c.prepareStatement(sql);
        statement.setLong(1, nextStateId++);
        statement.setLong(2, state.getTimestamp());
        byte[] bytes = encodeChunksWithIds(state.getChunks());
        byte[] bytesCompressed;
        try {
            bytesCompressed = ByteUtils.compressDeflate(bytes);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        statement.setBytes(3, bytesCompressed);
        statement.executeUpdate();
        statement.close();
    }

    public static byte[] encodeChunksWithIds(Chunk[][] chunks) {
        try (ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            DataOutput dataOutput = new DataOutputStream(baos);
            // write the length of the outer array
            dataOutput.writeInt(chunks.length);
            // write the length of the inner arrays
            dataOutput.writeInt(chunks[0].length);
            for (int i = 0; i < chunks.length; i++) {
                for (int j = 0; j < chunks[i].length; j++) {
                    dataOutput.writeLong(chunks[i][j].getId());
                }
            }
            return baos.toByteArray();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    public static Chunk[][] decodeChunksFromIds(byte[] buffer) {
        try (ByteArrayInputStream bais = new ByteArrayInputStream(buffer)) {
            DataInput dataInput = new DataInputStream(bais);
            // read the length of the outer array
            int outer = dataInput.readInt();
            // read the length of the inner arrays
            int inner = dataInput.readInt();
            Chunk[][] chunks = new Chunk[outer][inner];
            for (int i = 0; i < chunks.length; i++) {
                for (int j = 0; j < chunks[i].length; j++) {
                    Chunk chunk = new Chunk();
                    chunk.setId(dataInput.readLong());
                    chunks[i][j] = chunk;
                }
            }
            return chunks;
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public List<State> getLastStates(int limit) throws SQLException, IOException, DataFormatException {
        String sql = "SELECT ltimestamp, chunkids from states ORDER BY id DESC LIMIT " + limit;
        Statement statement = c.createStatement();
        ResultSet rs = statement.executeQuery(sql);

        List<State> states = new ArrayList<>();

        if (!rs.next()) {
            statement.close();
            return states;
        }

        do {
            State state = new State();
            state.setTimestamp(rs.getLong("ltimestamp"));
            byte[] encoded = ByteUtils.decompressDeflate(rs.getBytes("chunkids"));
            Chunk[][] chunks = decodeChunksFromIds(encoded);
            state.setChunks(chunks);
            states.add(state);
        } while(rs.next());

        statement.close();
        return states;
    }

    @Override
    public List<State> getDrawableStates(List<State> states, int limit) throws SQLException {
        List <State> stateList = new ArrayList<>();
        stateLoop:
        for (State state : states) {
            Chunk[][] chunks = state.getChunks();
            for (int row = 0; row < chunks.length; row++) {
                for (int col = 0; col < chunks[row].length; col++) {
                    Chunk chunk = chunks[row][col];
                    long id = chunk.getId();
                    chunk = getChunkById(id);
                    if (chunk == null) {
                        // image not persisted, try the next state
                        continue stateLoop;
                    }
                    chunks[row][col] = chunk;
                }
            }
            // all chunks available
            stateList.add(state);
            if (limit-- > 0) {
                continue;
            } else {
                break;
            }
        }
        return stateList;
    }

    @Override
    public List<State> getAllDrawableStates(int limit) throws SQLException, IOException, DataFormatException {
        List<State> lastStates = getLastStates(limit);
        List<State> drawableStates = getDrawableStates(lastStates, limit);
        return drawableStates;
    }

    public BufferedImage getLastDrawableState() throws SQLException, IOException, DataFormatException {
        List<State> lastStates = getLastStates(2);

        List<State> drawableState = getDrawableStates(lastStates, 1);
        if (drawableState.isEmpty()) {
            logger.finest("No drawable state");
            return null;
        }

        Chunk[][] chunks = drawableState.get(0).getChunks();

        return ImageHelper.createImageFromChunks(chunks);
    }
}
