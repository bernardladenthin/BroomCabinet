// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.Objects;

/**
 * Where a database is and which schema of it to use. The driver is found by
 * {@link DriverManager} from the URL, so any JDBC driver on the class path works.
 *
 * @param url      the JDBC URL
 * @param user     may be {@code null} when the URL or the driver needs none
 * @param password may be {@code null}; never part of {@link #toString()}
 * @param schema   may be {@code null}: the source then uses the connection's current schema,
 *                 the target creates its tables unqualified
 */
public record ConnectionSpec(String url, String user, String password, String schema) {

    /** Shown instead of a password. */
    public static final String MASK = "****";

    public ConnectionSpec {
        Objects.requireNonNull(url, "url");
    }

    public Connection open() throws SQLException {
        if (user == null) {
            return DriverManager.getConnection(url);
        }
        return DriverManager.getConnection(url, user, password);
    }

    @Override
    public String toString() {
        return "ConnectionSpec{url='" + url + "', user='" + user + "', password=" + (password == null ? "null" : MASK)
                + ", schema='" + schema + "'}";
    }
}
