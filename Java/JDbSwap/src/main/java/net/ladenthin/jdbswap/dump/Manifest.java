// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap.dump;

import java.util.List;

import net.ladenthin.jdbswap.jdbc.Column;

/**
 * The content of {@value DumpFormat#MANIFEST}. An export rewrites it after every finished
 * table, so an interrupted export still leaves a dump of the tables it completed.
 *
 * @param formatVersion {@link DumpFormat#VERSION} of the build that wrote it
 * @param tables        in export order
 */
public record Manifest(int formatVersion, List<Table> tables) {

    /**
     * @param name    as stored in the source
     * @param columns in column order, each with the longest value measured
     * @param rows    rows written over all parts
     * @param parts   part {@code i} of the list is part {@code i} of the export
     */
    public record Table(String name, List<Column> columns, long rows, List<Part> parts) {
    }

    /**
     * @param file   relative to the dump directory
     * @param rows   rows in this part
     * @param sha256 hex digest of the uncompressed part
     */
    public record Part(String file, long rows, String sha256) {
    }
}
