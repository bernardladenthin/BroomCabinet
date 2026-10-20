<!--
SPDX-FileCopyrightText: 2016 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# JDbSwap

Moves whole database schemas from one JDBC database to another - written for **Impala →
Exasol**, usable for any pair - either through a directory of checksummed files or directly.

| Task | What it does |
|------|--------------|
| `export` | Reads every accepted table of the source schema and writes it as *N* gzip parts, round-robin, one writer thread per part. Records rows, SHA-256 and the longest value of every column in `dbswap.json`. |
| `import` | Recreates each table in the target and loads its parts in parallel, each into a staging table first. A part reaches the real table only after its SHA-256 matched. |
| `copy` | Source → target directly: no files, no checksum, single-threaded. |

A dump directory can be carried to where the target is, imported several times, and imported
table by table. The export rewrites `dbswap.json` after every finished table, so an aborted
export still leaves a usable dump of the tables it completed.

## Build

```bat
mvn clean verify
```

produces `target/jdbswap-1.0.0-SNAPSHOT-all.jar` with the Hive (for Impala), Exasol and
MonetDB drivers. Any other JDBC driver works when it is put on the class path:

```sh
java -cp jdbswap-1.0.0-SNAPSHOT-all.jar:ImpalaJDBC42.jar net.ladenthin.jdbswap.Main --task export ...
```

The tests need no database server: they run export, import and copy between in-memory H2
databases. The Hive, Exasol and MonetDB specifics are covered by unit tests, but have not been
run against real servers by the build.

## Usage

```sh
# export: Impala through the Hive driver
export DBSWAP_SOURCE_PASSWORD=...
java -Xmx16G -jar jdbswap-1.0.0-SNAPSHOT-all.jar --task export \
    --source-url 'jdbc:hive2://impala.example:21050/;auth=noSasl' --source-schema shop \
    --data-path /data/dump/shop --include '.*(orders).*' --exclude '.*(imported_orders).*'

# import: Exasol, 6 parts at a time
export DBSWAP_TARGET_PASSWORD=...
java -Xmx16G -jar jdbswap-1.0.0-SNAPSHOT-all.jar --task import \
    --target-url jdbc:exa:exasol.example:8563 --target-user sys --target-schema SHOP \
    --data-path /data/dump/shop --import-threads 6

# copy, without a dump
java -jar jdbswap-1.0.0-SNAPSHOT-all.jar --task copy \
    --source-url jdbc:... --target-url jdbc:monetdb://localhost:50000/demo
```

Every option can also be an environment variable: `--source-url` is `DBSWAP_SOURCE_URL`,
`--import-threads` is `DBSWAP_IMPORT_THREADS`, and so on. The command line wins. Put passwords
in the environment - a command line is visible to every user of the machine. Passwords never
appear in the log.

| Option | Default | Used by |
|--------|---------|---------|
| `--task` | - | `export`, `import` or `copy` |
| `--data-path` | - | export, import. Export writes only into a **new or empty** directory and deletes nothing. |
| `--source-url`, `--source-user`, `--source-password` | - | export, copy |
| `--source-schema` | the connection's current schema | export, copy |
| `--target-url`, `--target-user`, `--target-password` | - | import, copy |
| `--target-schema` | unqualified table names | import, copy |
| `--target-dialect` | `auto`: from the URL (`jdbc:exa:`, `jdbc:monetdb:`, else `generic`) | import, copy |
| `--table-prefix` | none | import, copy: put in front of every target table name |
| `--include` | `.*` | regex a table name must match completely |
| `--exclude` | none | regex that leaves a table out |
| `--parts` | `16` | export: part files and writer threads per table |
| `--import-threads` | `1` | import: parts loaded at the same time |
| `--batch-size` | `200000` | import, copy: rows per JDBC batch and commit |

Exit code `0` on success, `1` when the task failed (the log has the cause), `2` for a wrong
command line.

## Types

Values travel typed, in a canonical form the target gets back exactly:

| Source type | Carried as | Target column (generic) |
|-------------|------------|-------------------------|
| `CHAR`, `VARCHAR`, `STRING`, `CLOB`, unknown types | text | `CHAR(n)` up to 2000, else `VARCHAR(n)` |
| `TINYINT` ... `BIGINT` | `long` | the same integer type |
| `DECIMAL`, `NUMERIC` | `BigDecimal` | `DECIMAL(p, s)` (Exasol: `p` at most 36) |
| `FLOAT`, `REAL`, `DOUBLE` | `double` | `DOUBLE PRECISION` |
| `BOOLEAN` | `boolean` | `BOOLEAN` |
| `DATE`, `TIME`, `TIMESTAMP` | `Date`, `Time`, `Timestamp` | the same (Exasol has no `TIME`) |
| `BINARY`, `VARBINARY`, `BLOB` | bytes | `VARBINARY(n)`; MonetDB `BLOB`; Exasol has none |

A text or binary column keeps its declared length when the target can hold it. An unbounded
one - Impala's `STRING` - is created exactly as long as the longest value the export measured
(at least 1). A direct `copy` measured nothing and uses the dialect's maximum (Exasol
2,000,000, others 1,000,000).

Identifiers are quoted, so reserved words work as column names. In the target they are first
folded like an unquoted name: Impala's `orders` becomes `"ORDERS"` in Exasol.

## Dump directory (format 2)

| File | Content |
|------|---------|
| `dbswap.json` | format version, and per table: columns with type, size and longest value, rows, and per part its file, rows and SHA-256 |
| `0000-orders.part0003.gz` | part 3 of the first table |

Uncompressed, a part is every value of every row in column order, each a tag byte (`0` =
`NULL`, `1` = value) followed by its length as 4-byte `int` and its bytes (UTF-8 text, or the
raw bytes of a binary column). The SHA-256 covers these uncompressed bytes. The import also
refuses a part that holds more data than its rows, a manifest of another format version, and
part file names that would point outside the directory.

## Known limits

- Date and time values pass through the JVM's default time zone: run export and import in
  the same one (e.g. `-Duser.timezone=UTC` for both).
- An import drops and recreates its target tables. If a part fails, the import stops; the
  parts already loaded stay in the target table.
- Exasol: the import runs `REORGANIZE TABLE` after creating a table and `REORGANIZE DATABASE`
  after loading one, which needs the corresponding privileges.
