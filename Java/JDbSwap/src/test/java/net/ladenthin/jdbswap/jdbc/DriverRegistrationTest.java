// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.sql.DriverManager;
import java.sql.SQLException;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * {@link ConnectionSpec#open()} relies on {@link DriverManager} finding each bundled driver by
 * its URL, without {@code Class.forName}. That needs a {@code META-INF/services/java.sql.Driver}
 * entry per driver.
 */
public class DriverRegistrationTest {

    @ParameterizedTest
    @CsvSource({
            "jdbc:hive2://localhost:21050/;auth=noSasl, org.apache.hive.jdbc.HiveDriver",
            "jdbc:exa:localhost:8563, com.exasol.jdbc.EXADriver",
            "jdbc:monetdb://localhost:50000/db, nl.cwi.monetdb.jdbc.MonetDriver"})
    public void driverIsFoundByUrl(String url, String driverClass) throws SQLException {
        assertEquals(driverClass, DriverManager.getDriver(url).getClass().getName());
    }
}
