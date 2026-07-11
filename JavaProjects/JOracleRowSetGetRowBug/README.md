# OracleCachedRowSet `getRow()` after `afterLast()`

Minimal, self-contained reproducer for a JDBC-spec divergence in Oracle's
`oracle.jdbc.rowset.OracleCachedRowSet`.

## Summary

`OracleCachedRowSet.getRow()` returns the **total row count** when the cursor is positioned
*after the last row* (`afterLast()`), instead of `0`.

The JDK reference `CachedRowSet` (`com.sun.rowset.CachedRowSetImpl`, obtained via
`RowSetProvider.newFactory().createCachedRowSet()`) returns `0` in the same state, which is what
the JDBC specification requires.

> `java.sql.ResultSet.getRow()` — "Retrieves the current row number … **a value of `0` indicates
> that there is no current row.**"

When the cursor is `afterLast()` (or `beforeFirst()`) there is no current row, so a conforming
implementation must return `0`. `OracleCachedRowSet` does not.

## Why this matters

Code that restores or reasons about a cursor position using `getRow()` after iterating to the end
of a rowset silently behaves differently on Oracle's implementation than on the JDK reference (and
other implementations). Relying on `getRow()` at `afterLast()` therefore breaks portability.

## Root cause (short version)

Oracle's `getRow()` (decompiled) is `if (presentRow > rowCount) return rowCount; return presentRow;`.
At `afterLast()` the cursor field `presentRow == rowCount + 1`, so it clamps to `rowCount` instead of
returning `0`; `beforeFirst()` (`presentRow == 0`) is correct only incidentally. The JDK reference
guards the valid `1..N` range and falls through to `0` for any non-row position.

**Full decompiled analysis and a copy-paste-ready bug report: [`BUG.md`](BUG.md).**

## Driver-version availability (read this first)

The `oracle.jdbc.rowset` package (including `OracleCachedRowSet`) was **deprecated since ojdbc 12.2**
but still ships — and still exhibits the bug — in the **19.x and 21.x `ojdbc8` lines** (latest
checked: `19.27.0.0` and `21.21.0.0`, Dec 2025). Oracle **removed the entire package from the 23.x
driver jars**, verified on Maven Central: the `oracle/jdbc/rowset/` package is absent from `ojdbc8`
`23.2.0.0`, `23.9.0.25.07`, and `23.26.2.0.0`, and from `ojdbc11`/`ojdbc17` `23.26.2.0.0`. (Oracle's
lifecycle docs label the package "desupported in 26ai" and the 23ai/26ai JDBC Developer's Guide still
*describes* it — a documentation lag; the binaries no longer contain it.) So:

- This project **builds and reproduces the bug against 19.x / 21.x.**
- It **does not compile against any 23.x version** — `oracle.jdbc.rowset` no longer exists there.

The default `ojdbc.version` is therefore `21.21.0.0`, the newest release that still ships the class.

The defect is long-standing: independent public decompiled mirrors of ojdbc6 `11.2.0.2.0` and the
`10.2.0.2` driver contain a byte-identical `getRow()`, and no public report or Oracle bug ID names the
exact symptom. See [`BUG.md`](BUG.md) → "Prior art / related reports".

## Environment

| Component | Value |
|---|---|
| Java | 8 (source/target `1.8`) |
| Oracle driver | `com.oracle.database.jdbc:ojdbc8:${ojdbc.version}` (default `21.21.0.0`; must be a 19.x/21.x version) |
| Source `ResultSet` | H2 `com.h2database:h2:2.2.224` (in-memory; **no Oracle database required**) |

**No live Oracle database is needed.** `CachedRowSet.populate(ResultSet)` accepts *any*
`java.sql.ResultSet`, and the divergence is in the disconnected rowset's own cursor logic — not in
the data source or the SQL dialect. Both rowsets are populated from the *same* neutral H2 query, so
the only variable is the `CachedRowSet` implementation.

## Build & run

```bash
# Build (compiles for Java 8, runs the JUnit test, builds a runnable fat jar)
mvn clean package

# Run the demonstration
java -jar target/joraclerowsetgetrowbug-1.0.0-SNAPSHOT-jar-with-dependencies.jar
```

Convenience runner (no fat-jar rebuild), handy for the version walk below:

```bash
mvn -Dojdbc.version=19.27.0.0 compile exec:java
```

### Expected output (bug present)

```
Oracle JDBC driver under test : ojdbc8 21.21.0.0 (build property)
Driver self-reported version  : 21.21.0.0.0
Source query: SELECT 'value1' AS COL_A, 123 AS COL_B, CAST(NULL AS VARCHAR) AS COL_C UNION ALL SELECT 'value2', 456, 'not_null'

== com.sun.rowset.CachedRowSetImpl ==
  beforeFirst : getRow()=0 (isBeforeFirst=true)
  row 1       : getRow()=1
  row 2       : getRow()=2
  afterLast   : getRow()=0 (isAfterLast=true)  expected 0 per java.sql.ResultSet#getRow  OK

== oracle.jdbc.rowset.OracleCachedRowSet ==
  beforeFirst : getRow()=0 (isBeforeFirst=true)
  row 1       : getRow()=1
  row 2       : getRow()=2
  afterLast   : getRow()=2 (isAfterLast=true)  expected 0 per java.sql.ResultSet#getRow  <-- DIVERGENCE

Summary - getRow() while afterLast():
  reference implementation : 0
  OracleCachedRowSet       : 2
DIVERGENCE CONFIRMED: ...
```

(The fat jar shows `Driver self-reported version : unknown` because the assembled jar's merged
manifest loses the ojdbc `Implementation-Version`; the `mvn exec:java` run shows the real value.
The "build property" line is baked in at build time and is always accurate.)

## Version walk

The driver version is a single Maven property (`ojdbc.version`). Override it to test any release and
record the `afterLast()` value:

```bash
mvn -Dojdbc.version=<version> test                 # tripwire test
mvn -Dojdbc.version=<version> compile exec:java     # printed trace
```

| ojdbc8 version | ships `OracleCachedRowSet`? | `getRow()` at `afterLast()` | conforms (== 0)? |
|---|---|---|---|
| `19.27.0.0` | yes | **2** | no |
| `21.21.0.0` (default) | yes | **2** | no |
| `23.2.0.0` … `23.26.2.0.0` | **no — package removed** (verified on Maven Central) | n/a (does not compile) | n/a |

Every 19.x / 21.x release checked reproduces the divergence. The JUnit test
`oracleImpl_afterLast_divergesFromSpec` is a deliberate **tripwire**: it asserts the current
non-conforming behavior, so it turns **red** the moment a (19.x/21.x) driver version starts
returning `0` — telling you exactly where the behavior changed.

## Where to report

**Reported:** <https://github.com/oracle/ojdbc-extensions/issues/272>

- Public Oracle JDBC issues: <https://github.com/oracle/ojdbc-extensions>
- Stack Overflow with the `ojdbc` tag (the Oracle JDBC team monitors it)
- My Oracle Support (Service Request) — requires an Oracle support contract

## Contingencies

- If `OracleCachedRowSet` throws an NLS/i18n error at runtime, add
  `com.oracle.database.nls:orai18n` (matching version) — basic `populate`/`getRow` need only
  `ojdbc8` (verified with `21.21.0.0` and `19.27.0.0`).
- `OracleCachedRowSet.populate(ResultSet)` needs a source backed by a live `Statement`. A
  disconnected/hand-built `CachedRowSet` source makes `populate()` throw `NullPointerException`
  (`populateInit` → `getStatement().getMaxFieldSize()`); the JDK reference impl accepts it. This is
  why a live H2 `ResultSet` is used. The test `oracleImpl_populateFromDisconnectedSource_throwsNpe`
  pins this; see `BUG.md` → "Additional note".
- If the divergence ever fails to reproduce from the H2 source (not expected — it is cursor logic),
  swap in a real Oracle source via Testcontainers `org.testcontainers:oracle-free`; H2 remains the
  primary, dependency-light path here.
