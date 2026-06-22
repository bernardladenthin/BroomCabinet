# Bug report: `OracleCachedRowSet.getRow()` returns the row count after `afterLast()`

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

The divergence reproduces on every 19.x and 21.x release tested. The `oracle.jdbc.rowset` package
was removed entirely in the 23.x driver line (Oracle Database 23ai), so this report concerns the
maintained 19.x and 21.x lines. The same class ships in the equivalent `ojdbc11` builds and is
expected to behave identically; verified here on `ojdbc8`.

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

## Caveats

- The Oracle snippets are **decompiled bytecode** of a closed-source driver, specific to
  `21.21.0.0` (behavior identical on `19.27.0.0` by observation). Decompiler field names
  (`presentRow`, `rowCount`) may differ from Oracle's source identifiers, but the control flow is
  faithful and matches the observed output (`presentRow = rowCount + 1 = 3 > 2 → returns 2`).
