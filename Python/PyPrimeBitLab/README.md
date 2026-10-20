<!--
SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>

SPDX-License-Identifier: Apache-2.0
-->

# PyPrimeBitLab — primes as bit vectors, and a bench that tells a pattern from a hope

It starts with an observation anyone can make: every odd prime ends in a 1-bit. So perhaps the
other bits, arranged as vectors and matrices, say something about where the next prime is. This
project turns that idea into experiments — and, because almost every such idea *feels* like it
works on a few examples, into a **test bench** that measures every method the same way, against
the same reference, with controls that prove the bench can see a pattern when there is one.

Standard library only; `mpmath` is used for one cross-check if it happens to be installed.

    python primebitlab.py compare          # every experiment quietly, then one comparison table (~2 min)
    python primebitlab.py factor           # experiment 8 alone: factoring from the lowest digits (~5 s)
    python primebitlab.py all              # the same with every experiment's own output
    python primebitlab.py check 1000003    # a primality test through bit weights alone
    python primebitlab_test.py             # the ground truth the bench stands on

## The result first

**Nothing beats the sieve with the same divisors.** Every gain in the comparison table comes from
additional *divisibility* knowledge. Beyond the lowest bit, the binary digits of a prime carry no
usable information — which is what Mauduit–Rivat (2010) and Bourgain (2013/2015) proved. What
*can* be predicted are densities: the Riemann zeros explain 83 % of the variation of prime counts
in windows of 10 000 numbers, and Bateman–Horn predicts the primes on a quadratic curve to 0.6 %.

Nothing here is new mathematics. Every number below agrees with theory that is decades old. What
the project adds is the bench: a claim of "predicting primes" either survives this table or it
does not.

## The building blocks

| | |
|---|---|
| bit weights | for every divisor p, `n mod p = (b · w_p) mod p` with `w_p[j] = 2^j mod p`. The weight matrix is periodic with the order of 2 mod p — the period-3 case is the octal digit sum, the period-2 case the alternating bit sum (`weights`, `check`) |
| bit fields | a whole range is one Python `int`; each divisor is a periodic mask, the sieve is the AND of all masks (`wheel`) |
| residue number system | n as the vector (n mod 2, n mod 3, n mod 5, …). Divisibility is a 0 digit; a prime is a vector without one; the next prime is the next odometer reading where no wheel shows 0 (`rns`) |

## The bench

Primes up to `--limit` (10⁶), consecutive triples `(prev, p, q)` split **half for training, half
for testing**. The reference is the wheel of the first `--k` primes (2…13). Two metrics, the same
in every experiment:

| | | reference |
|---|---|---|
| **hits** | how often the next prime q after p is named correctly | wheel: 37.78 % |
| **bits/candidate** | the ideal code length an arithmetic coder would need for the prime bits of the test candidates, using the model's P(prime) | sieve random model W/ln c: 0.9622 |

The second metric exists because the first is blind. A weak feature never overturns "take the
first candidate", so every weak idea scores exactly 37.78 % — which says nothing either way. Bits
see a shift of a fraction of a percent.

"better"/"worse" is only said beyond 2 standard errors for hits, ±0.5 % for bits, and 4 σ where
many cells are compared at once. **Every experiment carries a positive control** ("c divisible
by 17/19", real sieve knowledge the wheel does not have) and the **"none" feature must reproduce
the wheel exactly** — `primebitlab_test.py` asserts both. A bench that cannot see the control
cannot see anything.

Learned models do not learn a probability but a **factor against W/ln c**. Primes are denser in
the training half (smaller numbers) than in the test half, and a model that learns raw rates
loses on the test half for that reason alone.

## The experiments

| | command | outcome |
|---|---|---|
| own features | `predict` | bits, Hamming weight, last gap: all ≈ the wheel. `p mod 30030` is *worse* (5760 classes, ~7 training cases each: it memorises noise) |
| Ramanujan filter bank | `ramanujan` | measures Hardy's coefficients μ(q)/φ(q) to 0.1 %. As a predictor it never beats "sieve to Q" with the same primes: the full expansion *is* the sieve in Fourier form |
| 1 compression | `compress` | zlib, bz2, lzma, context models on bits or history: none beats the sieve random model. The 17/19 control saves 8.5 % |
| 2 Lemke Oliver–Soundararajan | `bias` | the bias is there (15.4 % instead of 25 % same last digit) and the independent sieve random model reproduces the whole transition table (max. 2.1 σ) |
| 3 Riemann zeros | `zeta` | zeros computed from the Riemann–Siegel Z function. 34/35 prime powers ≤ 100 found from peaks; 83.5 % of window variation explained; ±0 for the single next prime |
| 4 Bateman–Horn | `poly` | 0.63 % mean error on twelve quadratics, against 56.7 % for the naive 1/ln |
| 5 learning | `learn` | logistic regression from bits learns nothing (with bit pairs it overfits); from the residue vector 17…31 it learns exactly "sieve to 31" |
| 6 sieve + Miller–Rabin | `nextprime` | 0 errors up to 10⁶; the next prime after 10¹⁰⁰ in ~7 ms. The binary representation pays off for *testing* (square-and-multiply walks the bits), not for predicting |
| 7 unexplored ranges | `unexplored` | random windows at 2⁴⁰…2²⁰⁰ and thin binary sets with open questions (weight 3, weight 5, fibbinary, binary palindromes): all within 2 σ of the sieve random model. The negative control n² − 1 = (n−1)(n+1) stands out at −8.1 σ |
| 8 factoring from below | `factor` | lifting N = a·b digit by digit from the lowest end leaves exactly φ(B^k) candidates after k digits, for every N: the low digits of N carry nothing about those of a factor. The full search costs N^0.502 against N^0.506 for trial division (Pollard rho: N^0.271) |

## The sieve random model has a range of validity

The first run of experiment 7 found 1 % too few primes at 2⁴⁰ (−3.1 σ). The primes were counted
correctly; the *model* was wrong. The density of numbers free of prime factors ≤ B departs from
the Mertens product Π(1 − 1/p) when u = ln x / ln B is small — measured −3.5 % at u ≈ 1.9,
+0.41 % ± 0.06 % at u ≈ 3.1, gone from u ≈ 5. That is the Buchstab function (1937). So windows
are now aligned with the prime number theorem (the deviation is shown as its own column), and
thin sets only use numbers with u ≥ 4. The remaining all-negative deviations of that run were
chance: 30 further windows gave −0.49 σ.

That is the procedure for anything that ever exceeds 4 σ here: new seed, more windows, and a
look at the model — before believing in a discovery.

## Factoring from the lowest digits

Experiment 8 takes up an old Java attempt (primecrash, 2016) to factor RSA-576 from below: keep
every pair (a mod 10^k, b mod 10^k) with a·b ≡ N mod 10^k, append a digit, repeat. It looks like
the last digits of N narrow the search. They do not: for every a with an inverse mod B^k, the
partner b = N·a⁻¹ is exactly one residue, so the candidates after k digits are φ(B^k) — the same
count for every N. The search walks through every residue a factor could have, √N of them, which
is trial division with all candidates held in memory at once. For RSA-576 that is about 2²⁹³ steps.

The old code had a second lesson. Its start filter dropped factors ending in 9, so 19·23 and
331·999979 could never be found — two of its own commented-out examples. A filter that silently
excludes the answer looks exactly like a method that does not work; `primebitlab_test.py` therefore
checks that the lifting finds *every* factorisation of N, not just the expected one.

## Adding an idea

Add a line to `RANK_FEATURES` (a function of `p, prev`) or `CANDIDATE_FEATURES` (a function of
`p, c`); `predict` measures it on both metrics and `compare` puts it in the table. To explore other
heights: `python primebitlab.py unexplored --heights 2^1000 10^500 --width 262144 --seed 5`.
