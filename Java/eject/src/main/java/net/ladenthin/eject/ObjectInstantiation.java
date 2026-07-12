// SPDX-FileCopyrightText: 2013-2014 Fraunhofer FOKUS
// SPDX-FileCopyrightText: 2013-2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.eject;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.*;

/**
 * Instantiate Java objects using a file contains a JSON encoded object.
 *
 * @author VSimRTI developer team <vsimrti@fokus.fraunhofer.de>
 * @author Bernard Ladenthin <bernard.ladenthin@fokus.fraunhofer.de>
 */
public class ObjectInstantiation<T> {

    /**
     * The class to instantiate.
     */
    private final Class<T> clazz;

    /**
     * Log messages to inform or debug.
     */
    private final StringBuilder logMessage = new StringBuilder();

    /**
     * The state.
     */
    private InstantiationState state = InstantiationState.Initialized;

    /**
     * This flag indicates that the default constructor should be used if the instantiation from a file does not work.
     */
    private final boolean tryDefaultConstructor;

    /**
     * This flag indicates that instantiated null objects are allowed.
     */
    private final boolean allowNull;

    /**
     * This flag indicates that a log will be created.
     */
    private final boolean createLog;

    /**
     * Constructor.
     *
     * @param clazz The class to instantiate.
     */
    public ObjectInstantiation(Class<T> clazz) {
        this(clazz, true, false, true);
    }

    /**
     * Constructor.
     *
     * @param clazz The class to instantiate.
     */
    public ObjectInstantiation(Class<T> clazz, boolean tryDefaultConstructor, boolean allowNull, boolean createLog) {
        appendLog(getClass().getSimpleName());
        appendLog(LogMessages.NEWLINE);
        appendLog(LogMessages.CLASS_TO_INSTANTIATE);
        appendLog(clazz.toString());
        appendLog(LogMessages.NEWLINE);
        this.clazz = clazz;
        this.tryDefaultConstructor = tryDefaultConstructor;
        this.allowNull = allowNull;
        this.createLog = createLog;
    }

    /**
     * Append a string representation of an object to the log.
     *
     * @param obj The object to log.
     */
    private void appendLog(Object obj) {
        if (createLog) {
            logMessage.append(String.valueOf(obj));
        }
    }

    /**
     * Append a string to the log.
     *
     * @param log The string to log.
     */
    private void appendLog(String log) {
        if (createLog) {
            logMessage.append(log);
        }
    }

    /**
     * Log if the file not exist.
     * @param file The file.
     */
    private void logFileNotExist(File file) {
        if (createLog) {
            String path;
            try {
                path = file.getCanonicalPath();
            } catch (IOException e) {
                path = "?";
            }
            appendLog(LogMessages.FILE_NOT_EXIST + path);
        }
    }

    /**
     * Read the file. If no file was found, the default constructor should be used.
     *
     * @param fileHandle The file to read.
     * @return The created object.
     * @throws InstantiationException The object could not be instantiated.
     */
    public T readFile(File fileHandle) throws InstantiationException {
        if (!state.equals(InstantiationState.Initialized)) {
            throw new IllegalStateException("The state is not the Initialized state.");
        }

        T obj = null;
        final Gson gson = new Gson();

        if (fileHandle.exists()) {
            if (fileHandle.canRead()) {
                try {
                    final BufferedReader reader = new BufferedReader(
                            new InputStreamReader(new FileInputStream(fileHandle)));
                    obj = gson.fromJson(reader, clazz);
                } catch (FileNotFoundException e) {
                    logFileNotExist(fileHandle);
                }
            } else {
                appendLog(LogMessages.FILE_CAN_NOT_READ);
            }
        } else {
            logFileNotExist(fileHandle);
        }

        if (obj != null) {
            state = state.transition(InstantiationState.ReadFileSuccessful);
            appendLog(LogMessages.FILE_FOUND);
            appendLog(LogMessages.NEWLINE);
        } else {
            state = state.transition(InstantiationState.ErrorReadingFile);
        }

        if (state.equals(InstantiationState.ErrorReadingFile)) {
            if (tryDefaultConstructor) {
                appendLog(LogMessages.NEWLINE);
                appendLog(LogMessages.TRY_DEFAULT_CONSTRUCTOR);
                appendLog(LogMessages.NEWLINE);
                try {
                    obj = clazz.newInstance();
                    state = state.transition(InstantiationState.DefaultConstructorSuccessful);
                    appendLog(LogMessages.DEFAULT_CONSTRUCTOR_USED);
                    appendLog(LogMessages.NEWLINE);
                } catch (InstantiationException | IllegalAccessException e) {
                    state = state.transition(InstantiationState.ErrorUsingDefaultConstructor);
                }
            } else {
                state = state.transition(InstantiationState.NoDefaultConstructor);
            }
        }

        if (obj == null && !allowNull) {
            appendLog(LogMessages.ERROR);
            appendLog(LogMessages.NEWLINE);
            throw new InstantiationException(LogMessages.ERROR.toString());
        }

        if (createLog) {
            final GsonBuilder builder = new GsonBuilder();
            builder.setPrettyPrinting();
            final Gson gsonPretty = builder.create();

            String normalString = gson.toJson(obj);
            String prettyString = gsonPretty.toJson(obj);

            appendLog(LogMessages.DIFFER);
            appendLog(LogMessages.NEWLINE);

            appendLog(LogMessages.NORMAL_STRING);
            appendLog(LogMessages.NEWLINE);
            appendLog(normalString);
            appendLog(LogMessages.NEWLINE);

            appendLog(LogMessages.PRETTY_STRING);
            appendLog(LogMessages.NEWLINE);
            appendLog(prettyString);
        }
        return obj;
    }

    /**
     * Get the log messages to inform or debug.
     *
     * @return The log messages.
     */
    public String getLogMessage() {
        return logMessage.toString();
    }

    /**
     * Check if a null objects are allowed.
     *
     * @return True if null objects are allowed, false otherwise.
     */
    public boolean isAllowNull() {
        return allowNull;
    }

    /**
     * Get the state of the {@link net.ladenthin.eject.ObjectInstantiation}.
     *
     * @return The state.
     */
    public InstantiationState getState() {
        return state;
    }

    /**
     * Get the class to instantiate.
     * @return The class to instantiate.
     */
    public Class<T> getClazz() {
        return clazz;
    }

    /**
     * Check if a log will be created.
     *
     * @return True if a log will be created, otherwise false.
     */
    public boolean isCreateLog() {
        return createLog;
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.Initialized</code>.
     *
     * @return True if the state equals <code>InstantiationState.Initialized</code>, false otherwise.
     */
    public boolean isStateInitialized() {
        return state.equals(InstantiationState.Initialized);
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.ErrorReadingFile</code>.
     *
     * @return True if the state equals <code>InstantiationState.ErrorReadingFile</code>, false otherwise.
     */
    public boolean isStateErrorReadingFile() {
        return state.equals(InstantiationState.ErrorReadingFile);
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.NoDefaultConstructor</code>.
     *
     * @return True if the state equals <code>InstantiationState.NoDefaultConstructor</code>, false otherwise.
     */
    public boolean isStateNoDefaultConstructor() {
        return state.equals(InstantiationState.NoDefaultConstructor);
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.DefaultConstructorSuccessful</code>.
     *
     * @return True if the state equals <code>InstantiationState.DefaultConstructorSuccessful</code>, false otherwise.
     */
    public boolean isStateDefaultConstructorSuccessful() {
        return state.equals(InstantiationState.DefaultConstructorSuccessful);
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.ErrorUsingDefaultConstructor</code>.
     *
     * @return True if the state equals <code>InstantiationState.ErrorUsingDefaultConstructor</code>, false otherwise.
     */
    public boolean isStateErrorUsingDefaultConstructor() {
        return state.equals(InstantiationState.ErrorUsingDefaultConstructor);
    }

    /**
     * Short function to check if the state equals <code>InstantiationState.ReadFileSuccessful</code>.
     *
     * @return True if the state equals <code>InstantiationState.ReadFileSuccessful</code>, false otherwise.
     */
    public boolean isStateReadFileSuccessful() {
        return state.equals(InstantiationState.ReadFileSuccessful);
    }

}
