// SPDX-FileCopyrightText: 2018 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jfileinventory;

import java.sql.SQLException;

public interface InventoryPersistence {
    void initConnection() throws ClassNotFoundException, SQLException;
    void initPersistence() throws SQLException;
    void insertFile(FileDescription fd) throws SQLException;

    void updateLastSeenByPath(long timestamp, String path) throws SQLException;

    FileDescription getFileByPath(String path) throws SQLException;
}
