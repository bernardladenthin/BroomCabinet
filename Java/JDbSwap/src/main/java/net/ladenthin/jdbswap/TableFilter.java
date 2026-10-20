// SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

package net.ladenthin.jdbswap;

import java.util.List;
import java.util.regex.Pattern;

/**
 * Which tables take part: a name must match {@code include} completely and must not match
 * {@code exclude} completely.
 *
 * @param include e.g. {@code .*(orders).*}
 * @param exclude e.g. {@code .*(imported_orders).*}; {@code null} excludes nothing
 */
public record TableFilter(Pattern include, Pattern exclude) {

    public static final TableFilter ALL = new TableFilter(Pattern.compile(".*"), null);

    public static TableFilter of(String include, String exclude) {
        return new TableFilter(Pattern.compile(include == null ? ".*" : include),
                exclude == null || exclude.isEmpty() ? null : Pattern.compile(exclude));
    }

    public boolean accepts(String table) {
        return include.matcher(table).matches() && (exclude == null || !exclude.matcher(table).matches());
    }

    public List<String> apply(List<String> tables) {
        return tables.stream().filter(this::accepts).toList();
    }

    @Override
    public String toString() {
        return "TableFilter{include='" + include + "', exclude='" + exclude + "'}";
    }
}
