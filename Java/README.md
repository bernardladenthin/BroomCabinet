<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# Java

Java projects and reference notes.

## Notes

- [`speak-better-java.md`](speak-better-java.md) — example-driven summary of Java
  best practices (equals/hashCode, collections, the memory model, immutability,
  patterns).
- [`java-collection-matrix.md`](java-collection-matrix.md) — feature-by-feature
  comparison table of the common collections, plus Mermaid diagrams of the type
  hierarchy (interfaces, abstract, concrete, concurrent, legacy).

## Projects

Each subdirectory is a standalone Maven project (its own `pom.xml`), built by the
`Java CI` GitHub Actions workflow (`.github/workflows/java-ci.yml`).

## Build hints

Build a single project from its own directory:

```bat
mvn clean install
```

### Check for dependency and plugin updates

Uses the [versions-maven-plugin](https://www.mojohaus.org/versions-maven-plugin/):

```bat
mvn versions:display-dependency-updates
mvn versions:display-plugin-updates
```

### Build into an isolated local repository

Keep the build from touching your default `~/.m2` repository by pointing
`maven.repo.local` at a throwaway directory:

```bat
mvn clean install -Dmaven.repo.local=C:\path\to\isolated-maven-repo
```

### Larger heap for the build

```bat
set MAVEN_OPTS=-Xms256m -Xmx512m
```

> Set `JAVA_HOME` to your JDK and put `%MAVEN_HOME%\bin` on `PATH`; verify with
> `mvn -v`.
