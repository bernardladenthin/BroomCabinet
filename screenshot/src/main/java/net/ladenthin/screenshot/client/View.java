package net.ladenthin.screenshot.client;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.beans.value.ChangeListener;
import javafx.beans.value.ObservableValue;
import javafx.collections.ObservableList;
import javafx.geometry.Insets;
import javafx.scene.Node;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.CheckBox;
import javafx.scene.control.Slider;
import javafx.scene.image.ImageView;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.HBox;
import javafx.scene.paint.Color;
import javafx.stage.Stage;
import net.ladenthin.screenshot.*;
import net.ladenthin.screenshot.byteprotocol.Message;
import net.ladenthin.screenshot.socket.Common;
import net.ladenthin.screenshot.socket.SecureClientRequestCycleSocket;
import net.ladenthin.screenshot.socket.ServerRequest;
import net.ladenthin.screenshot.socket.ServerResponse;

import java.awt.image.BufferedImage;
import java.io.IOException;
import java.sql.SQLException;
import java.util.*;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.zip.DataFormatException;

public class View extends Application {

    private static final Logger logger = Logger.getLogger(View.class.getName());

    private final static String host = "127.0.0.1";

    private BufferedImage stateImage;
    private ImageView iv, liveIv;

    private boolean isTimeSlide = false;
    private int rollbackValue;

    private final List<State> stateList = new ArrayList<>();

    private HBox centerBox, bottomBox;

    private CheckBox timeCheckbox;
    private Slider timeSlider;

    private volatile int windowHeight = 400;
    private volatile int windowWidth = 400;

    private final static Stack<Message> requestMessages = new Stack<>();
    private final static ImagePersistence imagePersistence = new ImagePersistenceImplSQLite("client.db");

    public static void main(String[] argv) {
        View.launch(argv);
    }

    @Override
    public void start(Stage stage) {

        LoggerHelper.seRootLoggerLevel(Level.FINEST);

        try {
            imagePersistence.initConnection();
            imagePersistence.initPersistence();
        } catch (ClassNotFoundException | SQLException e) {
            throw new RuntimeException(e);
        }

        byte[] key = ByteUtils.getSha256("Socket Password".getBytes(), "My Socket Salt".getBytes());

        Thread clientSocket = new Thread(new SecureClientRequestCycleSocket(host, Common.SERVER_PORT, key, new ServerRequest() {
            @Override
            public byte[] call() {
                try {
                    Thread.sleep(100);

                    Message requestMessage;

                    // there is no message available, get a new state
                    if (requestMessages.isEmpty()) {
                        requestMessage = new Message();
                        requestMessage.setRequestState(true);
                    } else {
                        requestMessage = requestMessages.pop();
                    }

                    if (logger.isLoggable(Level.FINEST)) {
                        logger.finest("");
                        logger.finest("");
                        logger.finest("===== CLIENT BEGIN =====");
                        logger.finest("requestMessage: " + requestMessage);
                        logger.finest("===== CLIENT END =====");
                        logger.finest("");
                        logger.finest("");
                    }

                    byte[] serialize = requestMessage.serialize();
                    return serialize;
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        }, new ServerResponse() {
            @Override
            public void call(byte[] response) {
                try {
                    Message responseMessage = new Message();
                    responseMessage.deserialize(response);

                    if (logger.isLoggable(Level.FINEST)) {
                        logger.finest("");
                        logger.finest("");
                        logger.finest("===== CLIENT BEGIN =====");
                        logger.finest("responseMessage: " + responseMessage);
                        logger.finest("===== CLIENT END =====");
                        logger.finest("");
                        logger.finest("");
                    }

                    Message requestMessage = new Message();
                    if (responseMessage.isResponseState()) {
                        State responseStateContainer = responseMessage.getResponseStateContainer();
                        imagePersistence.insertState(responseStateContainer);
                        Chunk[][] chunks = responseStateContainer.getChunks();
                        Collection<Long> requestChunkIds = new ArrayList<>();
                        for (int i = 0; i < chunks.length; i++) {
                            for (int j = 0; j < chunks[i].length; j++) {
                                long id = chunks[i][j].getId();
                                Chunk chunkById = imagePersistence.getChunkById(id);
                                if (chunkById == null) {
                                    requestChunkIds.add(id);
                                }
                            }
                        }
                        requestMessage.setRequestChunks(true);
                        requestMessage.setRequestChunkIds(requestChunkIds);
                    }

                    if(responseMessage.isResponseChunks()) {
                        Collection<Chunk> responseChunks = responseMessage.getResponseChunks();
                        for (Chunk chunk : responseChunks) {
                            Chunk chunkById = imagePersistence.getChunkById(chunk.getId());
                            if (chunkById == null) {
                                imagePersistence.insertChunk(chunk);
                            }
                        }
                        updateImage();
                        updateWindow();
                    }

                    requestMessage.setRequestState(true);
                    requestMessages.push(requestMessage);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        }), "ClientSocket");
        clientSocket.start();

        centerBox = new HBox();
        centerBox.setMinHeight(200);
        bottomBox = new HBox();

        bottomBox.setPadding(new Insets(15, 12, 15, 12));
        bottomBox.setSpacing(10);
        bottomBox.setStyle("-fx-background-color: #336699;");

        timeCheckbox = new CheckBox("Time Rollback");
        timeCheckbox.selectedProperty().addListener(new ChangeListener<Boolean>() {
            @Override
            public void changed(ObservableValue<? extends Boolean> observable, Boolean oldValue, Boolean newValue) {
                toggleTimeRollback(newValue);
            }
        });

        timeSlider = new Slider(0, 1, 1);
        timeSlider.setMinWidth(700);
        // disable by default
        timeSlider.setDisable(true);
        timeSlider.setShowTickLabels(true);
        timeSlider.setShowTickMarks(true);

        timeSlider.valueProperty().addListener(new ChangeListener<Number>() {
            @Override
            public void changed(ObservableValue<? extends Number> observable, Number oldValue, Number newValue) {
                setRollbackValue(newValue.intValue());
            }
        });

        bottomBox.getChildren().addAll(timeCheckbox, timeSlider);

        BorderPane border = new BorderPane();
        border.setCenter(centerBox);
        border.setBottom(bottomBox);

        Scene scene = new Scene(border);
        scene.setFill(Color.GRAY);

        stage.setTitle("Screensharing LivewView");
        stage.setWidth(1200);
        stage.setHeight(800);
        stage.setResizable(true);
        stage.setScene(scene);
        stage.sizeToScene();
        stage.show();

        scene.widthProperty().addListener(new ChangeListener<Number>() {
            @Override
            public void changed(ObservableValue<? extends Number> observableValue, Number oldSceneWidth, Number newSceneWidth) {
                changeWidth(newSceneWidth);
            }
        });
        scene.heightProperty().addListener(new ChangeListener<Number>() {
            @Override
            public void changed(ObservableValue<? extends Number> observableValue, Number oldSceneHeight, Number newSceneHeight) {
                changeHeight(newSceneHeight);
            }
        });
    }

    public void setRollbackValue(int value) {
        logger.finest("setRollbackValue: " + value);
        rollbackValue = value;
        updateWindow();
    }

    public void toggleTimeRollback(boolean enableRollback) {
        logger.finest("toggleTimeRollback: " + enableRollback);
        if (enableRollback) {
            timeSlider.setDisable(false);
            isTimeSlide = true;
            updateStateList();
        } else {
            timeSlider.setDisable(true);
            isTimeSlide = false;
        }
    }

    public void changeHeight(Number newSceneHeight) {
        logger.finest("changeHeight: " + windowHeight);
        windowHeight = newSceneHeight.intValue();
        updateWindow();
    }

    public void changeWidth(Number newSceneWidth) {
        logger.finest("changeWidth: " + windowWidth);
        windowWidth = newSceneWidth.intValue();
        updateWindow();
    }

    public void updateImage() throws SQLException, IOException, DataFormatException {
        stateImage = imagePersistence.getLastDrawableState();
        if (stateImage == null) {
            liveIv = null;
            return;
        }
        liveIv = ImageHelper.createImageViewFromBufferedImage(stateImage);
    }

    public void updateStateList() {
        stateList.clear();
        try {
            SortedSet<State> drawableStates = new TreeSet<>(imagePersistence.getAllDrawableStates(100));
            stateList.addAll(drawableStates);
            timeSlider.setMin(0);
            timeSlider.setMax(stateList.size()-1);
        } catch (Exception e) {
            logger.log(Level.INFO, e.getMessage(), e);
        }
    }

    public void updateWindow() {
        logger.finest("#updateWindow");
        try {

            if (isTimeSlide) {
                // the rollbackValue maybe wrong and uninitialized
                if (rollbackValue > stateList.size()-1 || rollbackValue < 0) {
                    iv = null;
                } else {
                    State selectedState = stateList.get(rollbackValue);
                    BufferedImage imageFromChunks = ImageHelper.createImageFromChunks(selectedState.getChunks());
                    iv = ImageHelper.createImageViewFromBufferedImage(imageFromChunks);
                }
            } else {
                iv = liveIv;
            }

            if (iv == null) {
                return;
            }

            if (iv.getImage().getWidth() > windowWidth) {
                iv.setFitWidth(windowWidth);
            }

            // min cap to 1 pixel height
            int maxHeight = Math.max(1, windowHeight - (int)bottomBox.getHeight());

            if (iv.getImage().getHeight() > maxHeight) {
                iv.setFitHeight(maxHeight);
            }
            iv.setPreserveRatio(true);
            iv.setSmooth(true);
            iv.setCache(true);

            Platform.runLater(new Runnable() {
                @Override
                public void run() {
                    //Update UI here
                    synchronized (centerBox) {
                        ObservableList<Node> children = centerBox.getChildren();
                        children.clear();
                        children.add(iv);
                        /*
                        if (children.isEmpty()) {
                            logger.info("Don't know how this is possible :(");
                        } else {
                            centerBox.getChildren().clear();
                        }
                        */
                    }
                }
            });
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
