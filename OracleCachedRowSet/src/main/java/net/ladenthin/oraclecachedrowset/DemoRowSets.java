// @formatter:off
/**
 * Copyright 2026 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */
// @formatter:on
package net.ladenthin.oraclecachedrowset;

import java.io.IOException;
import java.io.InputStream;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Properties;

import javax.sql.rowset.CachedRowSet;
import javax.sql.rowset.RowSetProvider;

import oracle.jdbc.rowset.OracleCachedRowSet;

/**
 * Builds two {@link CachedRowSet} instances populated from the <em>same</em> neutral source
 * {@link ResultSet}: the JDK reference implementation and Oracle's
 * {@link OracleCachedRowSet}. The only variable between them is the implementation, which
 * isolates the {@code getRow()} divergence demonstrated by {@link Main} and the tests.
 *
 * <p>The source rows come from an H2 in-memory database. H2 is incidental &mdash; it merely
 * provides a real {@link ResultSet} to call {@link CachedRowSet#populate(ResultSet)} with;
 * <strong>no live Oracle database is required</strong> because the divergence lives in the
 * disconnected rowset's own cursor logic, not in the data source or the SQL dialect.</p>
 */
public final class DemoRowSets {

    /** JDBC URL of the throwaway in-memory H2 database used only as a {@link ResultSet} source. */
    public static final String H2_URL = "jdbc:h2:mem:rowsetbug";

    /**
     * A dialect-neutral query that yields exactly two rows with three columns, the third of
     * which is {@code NULL} in the first row. It deliberately avoids Oracle-only constructs
     * ({@code DECODE}, {@code DUAL}, {@code CONNECT BY ROWNUM}); the row count and the
     * NULL-in-row-1 shape are the only things that matter for the demonstration.
     */
    public static final String SQL =
            "SELECT 'value1' AS COL_A, 123 AS COL_B, CAST(NULL AS VARCHAR) AS COL_C "
            + "UNION ALL "
            + "SELECT 'value2', 456, 'not_null'";

    /** Number of rows {@link #SQL} produces. */
    public static final int ROW_COUNT = 2;

    /** Classpath location of the Maven-filtered build properties. */
    private static final String BUILD_PROPERTIES = "/net/ladenthin/oraclecachedrowset/build.properties";

    private DemoRowSets() {
        // utility class
    }

    /**
     * Returns the Oracle JDBC driver version this artifact was built against, read from the
     * Maven-filtered {@code build.properties} on the classpath. Unlike
     * {@link #oracleDriverVersion()} (which reads the jar manifest and is lost in the merged
     * fat jar), this value is always available and exactly matches the {@code ojdbc.version}
     * the build used.
     *
     * @return the build-time {@code ojdbc.version}, or a descriptive fallback when unavailable
     */
    public static String configuredOjdbcVersion() {
        try (InputStream in = DemoRowSets.class.getResourceAsStream(BUILD_PROPERTIES)) {
            if (in == null) {
                return "unknown (build.properties not on classpath)";
            }
            Properties props = new Properties();
            props.load(in);
            String version = props.getProperty("ojdbc.version");
            return version == null || version.isEmpty() ? "unknown" : version;
        } catch (IOException e) {
            return "unknown (" + e.getMessage() + ")";
        }
    }

    /**
     * Creates the JDK reference {@link CachedRowSet} (typically
     * {@code com.sun.rowset.CachedRowSetImpl}) populated from {@link #SQL}.
     *
     * @return a populated reference {@link CachedRowSet}, cursor positioned before the first row
     * @throws SQLException if the rowset cannot be created or populated
     */
    public static CachedRowSet referenceCachedRowSet() throws SQLException {
        CachedRowSet crs = RowSetProvider.newFactory().createCachedRowSet();
        populateFromH2(crs);
        return crs;
    }

    /**
     * Creates an Oracle {@link OracleCachedRowSet} populated from {@link #SQL}.
     *
     * @return a populated {@link OracleCachedRowSet}, cursor positioned before the first row
     * @throws SQLException if the rowset cannot be created or populated
     */
    public static CachedRowSet oracleCachedRowSet() throws SQLException {
        CachedRowSet crs = new OracleCachedRowSet();
        populateFromH2(crs);
        return crs;
    }

    /**
     * Returns the Oracle JDBC driver version reported by the {@link OracleCachedRowSet} jar's
     * manifest, or a placeholder when the manifest does not carry one.
     *
     * @return the {@code Implementation-Version} of the ojdbc jar, or a descriptive fallback
     */
    public static String oracleDriverVersion() {
        Package pkg = OracleCachedRowSet.class.getPackage();
        String version = pkg == null ? null : pkg.getImplementationVersion();
        return version == null ? "unknown (ojdbc manifest had no Implementation-Version)" : version;
    }

    /**
     * Opens a fresh H2 connection, runs {@link #SQL}, and populates the given (disconnected)
     * {@link CachedRowSet}. The JDBC resources are closed immediately afterwards because a
     * populated {@link CachedRowSet} keeps its own in-memory copy of the data.
     *
     * @param target the rowset to populate
     * @throws SQLException if the query fails or the rowset cannot be populated
     */
    private static void populateFromH2(CachedRowSet target) throws SQLException {
        // Register H2 explicitly: the runnable fat jar merges every dependency's
        // META-INF/services/java.sql.Driver into one file, so H2's automatic
        // ServiceLoader registration would be clobbered by the Oracle driver's.
        try {
            Class.forName("org.h2.Driver");
        } catch (ClassNotFoundException e) {
            throw new SQLException("H2 JDBC driver (org.h2.Driver) is not on the classpath", e);
        }
        try (Connection connection = DriverManager.getConnection(H2_URL);
                Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(SQL)) {
            target.populate(resultSet);
        }
    }
}
