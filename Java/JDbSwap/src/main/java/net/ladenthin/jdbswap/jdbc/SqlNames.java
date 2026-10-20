// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.jdbc;

import java.sql.DatabaseMetaData;
import java.sql.SQLException;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;

/**
 * Quotes identifiers so that reserved words and unusual names survive.
 *
 * <p>A quoted identifier is case-sensitive, an unquoted one is folded by most databases. For
 * the target, {@link #target(String)} therefore folds a name the way the database folds an
 * unquoted one before quoting it: {@code orders} from Impala becomes {@code "ORDERS"} in
 * Exasol, the same table an unquoted {@code CREATE TABLE orders} would create.</p>
 */
public final class SqlNames {

    /** How a database stores identifiers that were not quoted. */
    public enum Case {
        UPPER, LOWER, AS_IS
    }

    private final String quote;
    private final Case unquotedCase;

    /**
     * @param quote        the identifier quote; empty when the database cannot quote
     * @param unquotedCase how the database folds unquoted identifiers
     */
    public SqlNames(String quote, Case unquotedCase) {
        this.quote = quote;
        this.unquotedCase = unquotedCase;
    }

    /** Reads quote and case from the driver; a driver that does not tell gets no quoting. */
    public static SqlNames of(DatabaseMetaData metaData) {
        String quote;
        try {
            quote = metaData.getIdentifierQuoteString();
        } catch (SQLException e) {
            quote = null;
        }
        // JDBC: a space means quoting is not supported
        if (quote == null || quote.isBlank()) {
            quote = "";
        }

        Case unquotedCase;
        try {
            if (metaData.storesUpperCaseIdentifiers()) {
                unquotedCase = Case.UPPER;
            } else if (metaData.storesLowerCaseIdentifiers()) {
                unquotedCase = Case.LOWER;
            } else {
                unquotedCase = Case.AS_IS;
            }
        } catch (SQLException e) {
            unquotedCase = Case.AS_IS;
        }
        return new SqlNames(quote, unquotedCase);
    }

    /** {@code identifier} in quotes, embedded quotes doubled; unchanged without quoting. */
    public String quote(String identifier) {
        if (quote.isEmpty()) {
            return identifier;
        }
        return quote + identifier.replace(quote, quote + quote) + quote;
    }

    /** {@code identifier} folded the way this database folds unquoted identifiers. */
    public String normalize(String identifier) {
        return switch (unquotedCase) {
            case UPPER -> identifier.toUpperCase(Locale.ROOT);
            case LOWER -> identifier.toLowerCase(Locale.ROOT);
            case AS_IS -> identifier;
        };
    }

    /** A name for the target: folded, then quoted. */
    public String target(String identifier) {
        return quote(normalize(identifier));
    }

    /** {@code schema.table} of names already stored in this database (the source side). */
    public String qualified(String schema, String table) {
        return schema == null || schema.isEmpty() ? quote(table) : quote(schema) + "." + quote(table);
    }

    /** {@code schema.table} for the target; an empty schema leaves the table unqualified. */
    public String qualifiedTarget(String schema, String table) {
        return schema == null || schema.isEmpty() ? target(table) : target(schema) + "." + target(table);
    }

    /** The quoted column names, comma separated, in their order. */
    public String columnList(List<Column> columns, boolean forTarget) {
        return columns.stream()
                .map(column -> forTarget ? target(column.name()) : quote(column.name()))
                .collect(Collectors.joining(", "));
    }

    /** {@code ?, ?, ?} with one placeholder per column. */
    public static String placeholders(int count) {
        return String.join(", ", Collections.nCopies(count, "?"));
    }
}
