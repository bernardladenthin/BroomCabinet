<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# JMinifloat

An educational **8-bit minifloat** that models IEEE-754 floating-point mechanics
in a form small enough to trace by hand.

## Format

```
[ S | E E E | M M M M ]
  0   1 2 3   4 5 6 7
```

* **Sign** — bit 0
* **Exponent** — bits 1–3, excess-3 (bias 3): stored `000..111` → actual `-3..+4`
* **Mantissa** — bits 4–7, with an implicit hidden leading `1` for normalized numbers

The eight bits are packed into the low byte of an `int`. The class demonstrates
normalized/denormalized numbers, ±0, ±∞, NaN, overflow/underflow, and addition.

## Usage

```java
new Minifloat(1.5).getValue();                 // 1.5
new Minifloat(100.0).getValue();               // Infinity (overflow)
Minifloat a = new Minifloat(1.0);
a.add(new Minifloat(2.0));
a.getValue();                                  // 3.0
Minifloat.bitsToMinifloat("01110000".toCharArray()).getValue(); // Infinity
```

## Build & test

```bash
mvn clean verify
```

## Implementation notes

This is an original implementation of the (public, standard) minifloat format —
the eight bits are packed into an `int` and accessed with shifts/masks; encoding
uses `Math.getExponent`. See [Minifloat on Wikipedia](https://en.wikipedia.org/wiki/Minifloat)
for the general concept.

It deliberately handles two edge cases that are easy to get wrong:

1. `bitsToMinifloat(char[])` copies only the overlapping prefix: inputs shorter
   than 8 chars are zero-padded, longer inputs truncated (no
   `ArrayIndexOutOfBoundsException`).
2. Overflow (`> 15.5`) yields **±∞**, i.e. an all-ones exponent with a **zero**
   mantissa — an all-ones exponent with a non-zero mantissa would decode as NaN.

Both are covered by regression tests in `MinifloatTest`.

## Prior art

The same 1-3-4 excess-3 minifloat is used as a teaching example at Queen's
University (CISC101), with a partial Java implementation
[`Minifloat.java`](https://research.cs.queensu.ca/home/cisc101spring/Spring2006/webnotes/Minifloat.java)
(described in
[Java's Primitive Types Revisited](https://research.cs.queensu.ca/home/cisc101spring/Spring2006/webnotes/JavaPrimitiveTypes.html);
original author Richard Linley, revised by Jim Rodger). That file is referenced
for the concept only — this project shares no code with it.

While studying it, two bugs turned up in that course version, which this
implementation avoids (and pins with tests):

* **`bitsToMinifloat` crashes on inputs not exactly 8 chars long** — its copy
  loop is bounded by `Math.max(newBits.length, bits.length)`, so it reads/writes
  past the end and throws `ArrayIndexOutOfBoundsException` (should be `Math.min`).
* **Overflow produces NaN instead of ±∞** — the overflow branch sets *all*
  exponent and mantissa bits to `1`; since an all-ones exponent with a non-zero
  mantissa decodes as NaN, overflow never yields infinity (the mantissa bits must
  be cleared).
