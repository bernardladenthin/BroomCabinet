<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Bug report: `OracleCachedRowSet.getRow()` returns the row count after `afterLast()`

**Reported at:** <https://github.com/oracle/ojdbc-extensions/issues/272>

Copy-paste-ready report (e.g. for <https://github.com/oracle/ojdbc-extensions>, Stack Overflow tag
`ojdbc`, or My Oracle Support). The runnable reproducer lives in this folder; see `README.md` to
build and run it.

---

**Title:** `OracleCachedRowSet.getRow()` returns the row count instead of `0` when the cursor is `afterLast()` (violates the `java.sql.ResultSet#getRow()` contract)

## Summary

`oracle.jdbc.rowset.OracleCachedRowSet.getRow()` returns the **total number of rows** when the
cursor is positioned *after the last row* (`afterLast()`), instead of `0`.

The JDK reference implementation (`com.sun.rowset.CachedRowSetImpl`, via
`RowSetProvider.newFactory().createCachedRowSet()`) returns `0` in the same state, as required by
the JDBC specification.

## JDBC contract

[`java.sql.ResultSet.getRow()`](https://docs.oracle.com/en/java/javase/21/docs/api/java.sql/java/sql/ResultSet.html#getRow()):

> Retrieves the current row number. […] **a value of `0` indicates that there is no current row.**

When the cursor is `afterLast()` (or `beforeFirst()`) there is no current row, so a conforming
implementation must return `0`.

## Affected versions

| ojdbc8 version | `getRow()` at `afterLast()` | conforms? |
|---|---|---|
| `19.27.0.0` (latest 19.x) | `2` | no |
| `21.21.0.0` (latest 21.x) | `2` | no |

The divergence reproduces on every 19.x and 21.x release tested.

**Availability timeline** (verified against the actual jars on Maven Central):

- **Deprecated since 12.2.** Oracle's JDBC Developer's Guide ("Changes in This Release", 12.2)
  deprecated the `oracle.jdbc.rowset` package and recommends the standard JDK rowset instead.
- **Present and buggy through the 19.x and 21.x lines** — `oracle.jdbc.rowset.OracleCachedRowSet`
  is in `ojdbc8` `19.27.0.0` and `21.21.0.0` and exhibits the bug.
- **Physically absent from the 23.x driver jars** — the entire `oracle/jdbc/rowset/` package is gone
  from `ojdbc8` `23.2.0.0`, `23.9.0.25.07`, and `23.26.2.0.0`, and from `ojdbc11`/`ojdbc17`
  `23.26.2.0.0` (confirmed by listing the jar contents). Oracle's lifecycle docs label the package
  "desupported in 26ai".
- **Documentation-lag caveat:** the 23ai/26ai JDBC Developer's Guide still *describes* the package,
  so a documentation-based search may conclude it "still ships" — but the binaries do not contain it.

This report therefore concerns the maintained 19.x and 21.x lines. The class is `ojdbc8` here; the
equivalent `ojdbc11`/`ojdbc17` builds carry the same code and are expected to behave identically.

## Environment

- **Driver:** `com.oracle.database.jdbc:ojdbc8` `21.21.0.0` and `19.27.0.0`
- **JVM:** OpenJDK 21 (behavior is JVM-version independent)
- **Comparison baseline:** `com.sun.rowset.CachedRowSetImpl`
- **Data source:** H2 `2.2.224`, used only to provide a neutral source `ResultSet`. **No Oracle
  database is required** — `CachedRowSet.populate(ResultSet)` accepts any `ResultSet`, and the
  divergence is in the disconnected rowset's own cursor logic, not in the data or SQL dialect. Both
  rowsets are populated from the *identical* source, so the only variable is the implementation.

## Steps to reproduce

`pom.xml` dependencies:

```xml
<dependency>
  <groupId>com.oracle.database.jdbc</groupId>
  <artifactId>ojdbc8</artifactId>
  <version>21.21.0.0</version>
</dependency>
<dependency>
  <groupId>com.h2database</groupId>
  <artifactId>h2</artifactId>
  <version>2.2.224</version>
</dependency>
```

`OracleCachedRowSetGetRow.java`:

```java
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

import javax.sql.rowset.CachedRowSet;
import javax.sql.rowset.RowSetProvider;

import oracle.jdbc.rowset.OracleCachedRowSet;

public class OracleCachedRowSetGetRow {

    // OracleCachedRowSet.populate(...) requires a ResultSet backed by a real
    // Statement, so use any live JDBC source. H2 in-memory keeps it dependency-light.
    private static final String URL = "jdbc:h2:mem:demo";
    private static final String SQL = "SELECT 'a' AS C1 UNION ALL SELECT 'b'";

    public static void main(String[] args) throws Exception {
        report("reference", RowSetProvider.newFactory().createCachedRowSet());
        report("oracle   ", new OracleCachedRowSet());
    }

    private static void report(String label, CachedRowSet crs) throws SQLException {
        try (Connection c = DriverManager.getConnection(URL);
             Statement s = c.createStatement();
             ResultSet rs = s.executeQuery(SQL)) {
            crs.populate(rs);
        }
        while (crs.next()) {
            // advance the cursor to afterLast()
        }
        System.out.println(label + ": " + crs.getClass().getName()
            + " | isAfterLast=" + crs.isAfterLast()
            + " | getRow()=" + crs.getRow() + "  (JDBC spec requires 0)");
    }
}
```

## Expected

`getRow()` returns `0` at `afterLast()` (as the reference implementation does).

## Actual

```
reference: com.sun.rowset.CachedRowSetImpl | isAfterLast=true | getRow()=0  (JDBC spec requires 0)
oracle   : oracle.jdbc.rowset.OracleCachedRowSet | isAfterLast=true | getRow()=2  (JDBC spec requires 0)
```

## Root cause

*(Oracle side decompiled from `ojdbc8` `21.21.0.0` with CFR; field names are the decompiler's. The
JDK side is OpenJDK `com.sun.rowset.CachedRowSetImpl`.)*

Both implementations use the same cursor model: an index that is `0` before the first row, `1..N`
while on a row, and `N+1` after the last row (`N` = row count). In `OracleCachedRowSet` this field is
`presentRow`; `next()` sets it to `rowCount + 1` when it steps off the last row, and `isAfterLast()`
tests `presentRow == rowCount + 1`:

```java
// OracleCachedRowSet (decompiled)
public boolean next() throws SQLException {
    ...
    if (presentRow + 1 <= rowCount) { ++presentRow; ...; return true; }
    presentRow = rowCount + 1;          // step into the afterLast position
    return false;
}
public boolean isAfterLast() throws SQLException {
    return rowCount > 0 && presentRow == rowCount + 1;
}
```

The defect is solely in `getRow()`:

```java
// OracleCachedRowSet (decompiled)
public int getRow() throws SQLException {
    if (presentRow > rowCount) {   // true exactly when afterLast (presentRow == rowCount + 1)
        return rowCount;           // <-- clamps to N instead of returning 0
    }
    return presentRow;
}
```

When the cursor is `afterLast()`, `presentRow == rowCount + 1`, so `presentRow > rowCount` is true
and the method returns `rowCount` (`2`). That first branch looks like an intended upper-bound clamp,
but the `afterLast` position is precisely "no current row", for which the JDBC contract requires `0`.
(The `beforeFirst` case is correct only incidentally: there `presentRow == 0`, which skips the clamp
and returns `presentRow`, i.e. `0`.)

By contrast the JDK reference returns `0` for *any* position outside `1..N`:

```java
// com.sun.rowset.CachedRowSetImpl (OpenJDK)
public int getRow() throws SQLException {
    if (numRows > 0 && cursorPos > 0 && cursorPos < numRows + 1
            && !getShowDeleted() && !rowDeleted()) {
        return absolutePos;        // only when on a valid row
    }
    if (getShowDeleted()) {
        return cursorPos;
    }
    return 0;                      // beforeFirst AND afterLast both land here
}
```

The guard `cursorPos < numRows + 1` excludes the `afterLast` position (`cursorPos == numRows + 1`),
so it falls through to `return 0`.

## Suggested fix

Return `0` whenever the cursor is not on a valid row (covering both `beforeFirst` and `afterLast`):

```java
public int getRow() throws SQLException {
    if (presentRow < 1 || presentRow > rowCount) {
        return 0;   // no current row, per java.sql.ResultSet#getRow()
    }
    return presentRow;
}
```

## Impact

Code that reasons about or restores a cursor position via `getRow()` after iterating to the end of a
rowset silently behaves differently on `OracleCachedRowSet` than on the JDK reference (and other)
implementations, breaking portability across `CachedRowSet` providers.

## Additional note (secondary finding)

`OracleCachedRowSet.populate(ResultSet)` requires the source `ResultSet` to be backed by a live
`Statement`: populating from a disconnected/hand-built `CachedRowSet` source (one whose
`getStatement()` is `null`) throws `NullPointerException` in `OracleCachedRowSet.populateInit`
(`getStatement().getMaxFieldSize()`). The JDK reference implementation populates from the same source
without error. This is why the reproducer uses a live H2 `ResultSet` rather than a pure in-memory
`RowSetMetaDataImpl` source. Mentioned only to save reviewers the detour — the primary issue is the
`getRow()` divergence above.

## Prior art / related reports

A public search (Oracle MOS snippets, Oracle Communities, Stack Overflow, GitHub, blogs) found
**no report describing this exact symptom** (`getRow()` returning the row count after the last row)
and **no Oracle bug ID** for it. Supporting findings:

- **Independent confirmation of the root cause in public decompiled source.** Third-party decompiled
  mirrors of much older drivers contain a byte-for-byte identical `getRow()`:
  `github.com/caot/ojdbc6-11.2.0.2.0.src` (ojdbc6 11.2.0.2.0 — `getRow()` is
  `if (presentRow > rowCount) return rowCount; return presentRow;`) and
  `github.com/wenshao/OracleDriver10_2_0_2` (10.2.0.2, same body). The defect is therefore
  long-standing and stable across ~10.2 → 21.x — not a recent regression. (These are unofficial
  decompilations, but mutually consistent and identical to the `21.21.0.0` decompilation above.)
- **The correct guard already exists in the same class.** That same decompiled source validates the
  cursor elsewhere with `if (presentRow < 1 || presentRow > rowCount)` — i.e. exactly the suggested
  fix — so `getRow()` simply fails to reuse the bounds check the class already has.
- **Closest Oracle-acknowledged artifact:** My Oracle Support Doc **2741145.1**,
  "Java.sql.SQLException: Result Set After Last Row" (JDBC 12.2.0.0.0–19.7; reproduced on `ojdbc8`
  19.3/19.6, not 11.2; DB 19.8). It documents an after-last result-set defect that regressed into the
  19.x line — a plausible downstream symptom of this root cause — but is framed as a thrown exception,
  not as `getRow()`'s return value, and exposes no public bug number (login-gated).
- **Sibling classes:** `OracleWebRowSet`, `OracleFilteredRowSet`, and `OracleJoinRowSet` extend
  `OracleCachedRowSet` and inherit the same `getRow()`, so they share the defect. `OracleJDBCRowSet`
  is a thin wrapper that delegates to a live `ResultSet` and is not affected the same way.

## Caveats

- The Oracle snippets are **decompiled bytecode** of a closed-source driver, specific to
  `21.21.0.0` (behavior identical on `19.27.0.0` by observation). The control flow is faithful and
  matches the observed output (`presentRow = rowCount + 1 = 3 > 2 → returns 2`).
- The field names `presentRow`/`rowCount` are corroborated by the independent public decompiled
  mirrors above, so they are likely Oracle's actual identifiers rather than decompiler artifacts.
- The deprecation (12.2) and "desupported in 26ai" labels come from Oracle's documentation; the
  jar-content facts (present in 19.x/21.x, absent in 23.x) were verified directly on Maven Central.
