#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""Primes as bit vectors and bit fields -- and a test bench for every idea of predicting them.

THE STARTING IDEA. A number n is a bit vector b = (b0, b1, b2, ...) with n = sum(b_j * 2^j).
Every odd prime has b0 = 1; can the other bits, arranged as vectors and matrices, tell where the
next prime is? For every divisor p there is a weight vector w_p = (2^j mod p), and

    n mod p = (b . w_p) mod p          (dot product of bit vector and weight vector)

The weight matrix A[i][j] = 2^j mod p_i is periodic (period = order of 2 mod p). A whole range of
numbers is one bit field (a Python int): bit i set <=> i is still a candidate. Every divisor p
gives a periodic mask, and ANDing all masks is the sieve -- a pure vector operation.

WHAT THE BENCH ANSWERS. Every prediction method is measured on the same data: primes up to
--limit, consecutive primes (prev, p, q) split half for training, half for testing, against the
wheel of the first --k primes. Two metrics, the same everywhere:

    hits      how often the next prime q after p is named correctly        (reference: wheel)
    bits      ideal code length per wheel candidate, as an arithmetic       (reference: sieve
              coder would pack the prime bits with the model's P(prime)     random model W/ln c)

Hits are blind to weak effects (a weak feature never overturns "the first candidate"), bits are
not. Each experiment carries a positive control ("divisible by 17/19" -- real sieve knowledge) so
a bench that cannot see a pattern is told apart from a pattern that is not there.

THE RESULT, in one line: nothing beats the sieve with the same divisors. Every gain in the
comparison table comes from additional divisibility knowledge. Densities can be predicted (Riemann
zeros, Bateman-Horn); the single next prime cannot.

Basics:
    python primebitlab.py table   [--limit 64]
    python primebitlab.py weights [--max-p 31] [--width 12]
    python primebitlab.py check N
    python primebitlab.py wheel   [--limit 1000000] [--k 7]
    python primebitlab.py bits    [--limit 1000000] [--low 4]
    python primebitlab.py rns     [--start 89] [--count 25] [--next 1327]

Experiments on the common bench (all take [--limit 1000000] [--k 6]):
    python primebitlab.py predict      own features against the wheel
    python primebitlab.py ramanujan    Ramanujan filter bank          [--q 13 19 31 61 100]
    python primebitlab.py compress     1 compression test
    python primebitlab.py bias         2 Lemke Oliver-Soundararajan bias
    python primebitlab.py zeta         3 Riemann zeros                [--zeros 10 50 100 200 300] [--window 10000]
    python primebitlab.py poly         4 polynomials / Bateman-Horn   [--n 20000] [--bound 100000]
    python primebitlab.py learn        5 learning: bits against RNS    [--epochs 2]
    python primebitlab.py nextprime    6 sieve + Miller-Rabin         [--runs 20]
    python primebitlab.py unexplored   7 binary patterns at large heights [--heights 2^40 ... 2^200] [--seed 1]

    python primebitlab.py compare      every experiment quietly, then the comparison table
    python primebitlab.py all          everything with output, the comparison table at the end

Own prediction features: add a line to RANK_FEATURES or CANDIDATE_FEATURES.
Standard library only; mpmath is used for one cross-check if it happens to be installed.
"""

import argparse
import bz2
import contextlib
import functools
import io
import lzma
import math
import random
import sys
import time
import zlib
from bisect import bisect_right
from collections import Counter, defaultdict, namedtuple
from itertools import accumulate


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def popcount(x):
    return x.bit_count()


def small_primes(limit):
    """Primes <= limit by trial division (meant for small limits only)."""
    result = []
    for n in range(2, limit + 1):
        for p in result:
            if p * p > n:
                result.append(n)
                break
            if n % p == 0:
                break
        else:
            result.append(n)
    return result


def bit_vector(n, width):
    """Bit vector of n, LSB first: [b0, b1, ..., b_{width-1}]."""
    return [(n >> j) & 1 for j in range(width)]


def bin_str(n, width):
    """Binary representation MSB..LSB, the way one reads it."""
    return format(n, "0{}b".format(width))


def weight_vector(p, width):
    """w_p[j] = 2^j mod p."""
    return [pow(2, j, p) for j in range(width)]


def order_of_two(p):
    """Period of the weight vector: smallest k > 0 with 2^k ≡ 1 (mod p). None for p = 2."""
    if p == 2:
        return None
    k, x = 1, 2 % p
    while x != 1:
        x = (x * 2) % p
        k += 1
    return k


def mod_via_bits(n, p):
    """n mod p from the set bits and the weight vector alone."""
    width = max(1, n.bit_length())
    w = weight_vector(p, width)
    b = bit_vector(n, width)
    used = [w[j] for j in range(width) if b[j]]
    return sum(used) % p, used


MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)


def miller_rabin(n, bases=MR_BASES):
    """Miller-Rabin; with these bases deterministic for n < 3.3·10^24, above that error < 4^-13."""
    if n < 2:
        return False
    for p in MR_BASES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in bases:
        x = pow(a, d, n)                   # square-and-multiply: walks the bits of d one by one
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


# ---------------------------------------------------------------------------
# Bit fields: a whole range of numbers as one integer
# ---------------------------------------------------------------------------

def periodic_mask(p, length):
    """Bit i set if i is not divisible by p (0 <= i < length)."""
    mask, width = ((1 << p) - 1) ^ 1, p    # pattern of length p: bit 0 off, bits 1..p-1 on
    while width < length:                  # repeat the pattern by doubling
        mask |= mask << width
        width *= 2
    return mask & ((1 << length) - 1)


def stride_mask(p, offset, length):
    """Bits offset, offset+p, offset+2p, ... below length."""
    if offset >= length:
        return 0
    mask, width = 1, p
    while width < length - offset:
        mask |= mask << width
        width *= 2
    return (mask << offset) & ((1 << length) - 1)


def candidate_field(limit, divisors):
    """Bit field over 0..limit: every number divisible by none of the divisors (plus the divisors themselves)."""
    length = limit + 1
    field = ((1 << length) - 1) & ~0b11    # 0 and 1 are not prime
    for p in divisors:
        field &= periodic_mask(p, length)
        if p < length:
            field |= 1 << p
    return field


@functools.lru_cache(maxsize=None)
def prime_field(limit):
    """Exact prime bit field: AND the masks of every prime up to sqrt(limit)."""
    return candidate_field(limit, small_primes(math.isqrt(limit)))


def set_bits(x):
    """Indices of all set bits, ascending."""
    s = bin(x)[:1:-1]                      # digits without '0b', LSB first
    return [i for i, c in enumerate(s) if c == "1"]


# ---------------------------------------------------------------------------
# Basic commands
# ---------------------------------------------------------------------------

def cmd_table(args):
    primes = small_primes(args.limit)
    width = args.limit.bit_length()
    header = " ".join("b{}".format(j) for j in reversed(range(width)))
    print("Primes up to {} as bit vectors (MSB left, LSB right)\n".format(args.limit))
    print("{:>6}  {}   {}".format("n", "binary".ljust(width), header))
    for p in primes:
        cells = "  ".join(str(b) for b in reversed(bit_vector(p, width)))
        print("{:>6}  {}   {}".format(p, bin_str(p, width), " " + cells))
    odd = [p for p in primes if p != 2]
    print("\nLSB = 1 for all {} odd primes: {}".format(len(odd), all(p & 1 for p in odd)))


def cmd_weights(args):
    width = args.width
    print("Weight matrix A[p][j] = 2^j mod p  (n mod p = sum of the weights of all set bits)\n")
    print("{:>4} | {} | period".format("p", " ".join("{:>3}".format("b" + str(j)) for j in range(width))))
    print("-" * (8 + 4 * width + 10))
    for p in small_primes(args.max_p):
        row = " ".join("{:>3}".format(w) for w in weight_vector(p, width))
        period = order_of_two(p)
        print("{:>4} | {} | {}".format(p, row, "-" if period is None else period))
    print("\nExamples of the periodicity:")
    print("  p=3: period 2, weights 1,2 ≡ 1,-1  -> alternating bit sum (like the rule for 11 in decimal)")
    print("  p=7: period 3, weights 1,2,4       -> digit sum in octal (blocks of 3 bits)")
    print("  p=5: period 4, weights 1,2,4,3     -> digit sum of the hex digits, because 16 ≡ 1 (mod 5)")


def cmd_check(args):
    n = args.n
    width = max(1, n.bit_length())
    print("n = {}  =  {}b".format(n, bin_str(n, width)))
    print("set bits (positions): {}".format([j for j in range(width) if (n >> j) & 1]))
    if n < 2:
        print("-> not a prime")
        return
    divisors = small_primes(math.isqrt(n))
    print("Testing {} divisors up to sqrt(n) = {} through bit weights only:\n".format(len(divisors), math.isqrt(n)))
    shown = 0
    for p in divisors:
        r, used = mod_via_bits(n, p)
        assert r == n % p                  # control: the bit method computes exactly
        if r == 0 or shown < 12:
            weights = used if len(used) <= 12 else used[:12] + ["..."]
            print("  ÷{:<5} weights {} -> sum {} mod {} = {}".format(
                p, weights, sum(used), p, r))
            shown += 1
        if r == 0:
            print("\n-> {} is composite: {} = {} × {}".format(n, n, p, n // p))
            return
    if shown < len(divisors):
        print("  ... ({} more divisors, every remainder != 0)".format(len(divisors) - shown))
    print("\n-> {} is a prime".format(n))


def cmd_wheel(args):
    limit = args.limit
    primes = prime_field(limit)
    n_primes = popcount(primes)
    base = small_primes(100)[:args.k]
    print("Sieve as an AND of periodic bit masks over 0..{} ({} primes)\n".format(limit, n_primes))
    print("{:<26} {:>10} {:>9} {:>11} {:>10} {:>12}".format(
        "divisors", "period", "classes", "candidates", "share", "of them prime"))
    period, classes = 1, 1
    for k in range(1, len(base) + 1):
        p = base[k - 1]
        period *= p
        classes *= p - 1
        field = candidate_field(limit, base[:k])
        cand = popcount(field)
        hit = popcount(field & primes)
        label = ",".join(map(str, base[:k]))
        print("{:<26} {:>10} {:>9} {:>11} {:>9.1%} {:>12.1%}".format(
            label, period, classes, cand, cand / (limit + 1), hit / cand))
    print("\nWith every prime up to sqrt({}) = {} the bit field becomes exact (share prime = 100 %).".format(
        limit, math.isqrt(limit)))
    print("Each further divisor p only removes the share 1/p of the remaining candidates.")


def cmd_bits(args):
    limit, low = args.limit, args.low
    primes = [p for p in set_bits(prime_field(limit)) if p > 2]
    mod = 1 << low
    print("Lowest {} bits (= n mod {}) of the {} odd primes up to {}:\n".format(low, mod, len(primes), limit))
    counts = Counter(p % mod for p in primes)
    expected = 1 / (mod // 2)
    for r in range(1, mod, 2):
        share = counts[r] / len(primes)
        print("  ...{}  ({:>2})  {:>7.3%}   expected {:.3%}   dev. {:+.3%}".format(
            bin_str(r, low), r, share, expected, share - expected))
    print("\n-> Apart from LSB = 1 the low bits are equidistributed (Dirichlet's theorem).")

    width = limit.bit_length() - 1
    group = [p for p in primes if p.bit_length() == width]
    print("\nShare of 1-bits per position for the {} primes with exactly {} bits:\n".format(len(group), width))
    for j in reversed(range(width)):
        share = sum((p >> j) & 1 for p in group) / len(group)
        bar = "#" * round(share * 40)
        print("  b{:<3} {:>6.1%}  {}".format(j, share, bar))
    print("\n-> The middle bits sit at ~50 %; single bit positions carry hardly any information.")


def is_prime(n):
    return n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1))


def cmd_rns(args):
    start, count = args.start, args.count
    end = start + count - 1
    moduli = small_primes(math.isqrt(end))
    width = end.bit_length()
    print("Residue number system: n -> (n mod p) for every p ≤ sqrt({}) = {}".format(end, math.isqrt(end)))
    print("A digit (0) means: divisible by p. A prime is a vector without (0).\n")
    print("{:>7} |{} | prime | binary".format("n \\ p", "".join("{:>4}".format(p) for p in moduli)))
    print("-" * (8 + 4 * len(moduli) + 11 + width))
    for n in range(start, end + 1):
        digits = [n % p for p in moduli]
        cells = "".join(" (0)" if d == 0 else "{:>4}".format(d) for d in digits)
        prime = all(digits) or n in moduli
        print("{:>7} |{} | {:<5} | {}".format(n, cells, "yes" if prime else "", bin_str(n, width)))
    print("\n-> In binary, divisibility is smeared across every bit; in the RNS it sits in one digit.")

    n = args.next
    q = n + 1
    while not is_prime(q):
        q += 1
    steps = q - n
    moduli = small_primes(math.isqrt(q))
    shown = min(steps, 70)
    print("\nOdometer from n = {}: every wheel p counts n mod p onward; the next prime is the".format(n))
    print("first step t at which no wheel shows 0 (wheels up to sqrt({}) = {}).\n".format(q, math.isqrt(q)))
    print("{:>33} {}".format("step t (units):", "".join(str(t % 10) for t in range(1, shown + 1))))
    for p in moduli:
        digit = n % p
        print("  wheel {:>3}: at {:>3}, 0 in {:>3} |{}".format(
            p, digit, (-n) % p or p, "".join("0" if (n + t) % p == 0 else "·" for t in range(1, shown + 1))))
    if steps <= shown:
        print("{:>33} {}^".format("", " " * (steps - 1)))
    print("-> first column without a 0: t = {}, so {} is the next prime after {}.".format(steps, q, n))
    print("   That is exactly the sieve: every wheel covers one arithmetic progression of steps.")


# ---------------------------------------------------------------------------
# Common bench and comparison table
# ---------------------------------------------------------------------------

Bench = namedtuple("Bench", "limit primes primeset train test base cands baseline test_cands test_bits ref_bits")
RESULTS = []        # (experiment, method, metric, value, reference, verdict)


def prediction_data(limit):
    """Primes up to limit and triples (prev, p, q), split into a training and a test half."""
    primes = set_bits(prime_field(limit))
    triples = [t for t in zip(primes, primes[1:], primes[2:]) if t[0] >= 11]
    half = len(triples) // 2
    return primes, triples[:half], triples[half:]


@functools.lru_cache(maxsize=None)
def bench(limit, k=6):
    """The common ground of every comparison: same primes, same split, same wheel."""
    primes, train, test = prediction_data(limit)
    base = tuple(small_primes(100)[:k])
    cands = set_bits(candidate_field(limit, base))
    baseline = sum(rank_of(cands, p, q) == 1 for _, p, q in test) / len(test)
    primeset = frozenset(primes)
    # Second metric: every wheel candidate in the test range, cost in bits per candidate
    test_cands = [c for c in cands if c > test[0][1]]
    test_bits = [int(c in primeset) for c in test_cands]
    ref_bits = code_length(test_bits, [sieve_model(c, base) for c in test_cands]) / len(test_bits)
    return Bench(limit, primes, primeset, train, test, base, cands, baseline, test_cands, test_bits, ref_bits)


def print_bench(b):
    print("Bench: numbers up to {}, training up to p = {}, test: {} cases from p = {}".format(
        b.limit, b.train[-1][1], len(b.test), b.test[0][1]))
    print("References: wheel up to {} hits {:.2%}, sieve random model costs {:.4f} bits/candidate\n".format(
        b.base[-1], b.baseline, b.ref_bits))


@functools.lru_cache(maxsize=None)
def sieve_weight(divisors):
    """W = Π p/(p−1): wheel candidates are this much more often prime than arbitrary numbers (divisors as a tuple)."""
    return math.prod(p / (p - 1) for p in divisors)


def sieve_model(c, divisors):
    """Sieve random model: a wheel candidate c is prime with probability W / ln c."""
    return min(sieve_weight(divisors) / math.log(c), 0.999)


def code_length(bits, probs):
    """Ideal code length in bits (arithmetic coding) when probs are the predicted P(prime)."""
    total = 0.0
    for bit, p in zip(bits, probs):
        p = min(max(p, 1e-12), 1 - 1e-12)
        total -= math.log2(p if bit else 1 - p)
    return total


def record(experiment, method, metric, value, reference, verdict):
    RESULTS.append((experiment, method, metric, value, reference, verdict))


def verdict_hits(rate, ref, n):
    """Hit rates only count as different beyond 2 standard errors of the difference."""
    diff = rate - ref
    se = math.sqrt(2 * ref * (1 - ref) / n)
    return "better" if diff > 2 * se else "worse" if diff < -2 * se else "≈ same"


def verdict_lower(value, ref, tolerance):
    """For quantities where less is better (bits, errors, tests); tolerance relative to the reference."""
    if value < ref * (1 - tolerance):
        return "better"
    if value > ref * (1 + tolerance):
        return "worse"
    return "≈ same"


def wheel_ref(b):
    return "wheel up to {}: {:.2%}".format(b.base[-1], b.baseline)


def bits_ref(b):
    return "sieve model: {:.4f}".format(b.ref_bits)


def report(experiment, name, hits, b):
    rate = hits / len(b.test)
    verdict = verdict_hits(rate, b.baseline, len(b.test))
    print("  {:<42} {:>7.2%} {:>+8.2%}   {}".format(name, rate, rate - b.baseline, verdict))
    record(experiment, name, "hits", "{:.2%}".format(rate), wheel_ref(b), verdict)


def print_results():
    print("Comparison of every experiment on the common bench")
    current = None
    for experiment, method, metric, value, reference, verdict in RESULTS:
        if experiment != current:
            current = experiment
            print("\n{}".format(experiment))
        print("  {:<52} {:<14} {:>14}   {:<24} {}".format(method, metric, value, reference, verdict))


# ---------------------------------------------------------------------------
# Prediction features -- add your own ideas here
# ---------------------------------------------------------------------------
#
# Rank model: f(p, prev) depends on the prime p and its predecessor prev.
#   It learns at which position (1st, 2nd, 3rd, ... wheel candidate after p) the next prime
#   lies most often for this feature value.
#
# Candidate model: g(p, c) depends on the candidate c (and the current prime p).
#   For every feature value it learns by which factor such candidates are prime more or less
#   often than the sieve random model W/ln c expects. That gives π(c).
#   It predicts the candidate with the highest chance of being the next prime:
#   π_i · Π_{j<i} (1 - π_j). It is also measured how many bits per candidate the model would
#   need to pack the prime bits (as in the compression test).
#
# A feature must return a hashable value (int, bool, tuple, ...).
# "none" is the control each time and must reproduce the wheel result exactly.

RANK_FEATURES = [
    ("none (= plain wheel)", lambda p, prev: None),
    ("lowest 4 bits of p", lambda p, prev: p & 0b1111),
    ("bits b4..b7 of p", lambda p, prev: (p >> 4) & 0b1111),
    ("Hamming weight of p", lambda p, prev: popcount(p)),
    ("last gap p - prev", lambda p, prev: p - prev),
    ("lowest 4 bits + last gap", lambda p, prev: (p & 0b1111, p - prev)),
    ("p mod 30030 (wheel residue class)", lambda p, prev: p % 30030),
]

CANDIDATE_FEATURES = [
    ("none (= plain wheel)", lambda p, c: None),
    ("lowest 4 bits of c", lambda p, c: c & 0b1111),
    ("bits b4..b7 of c", lambda p, c: (c >> 4) & 0b1111),
    ("Hamming weight of c", lambda p, c: popcount(c)),
    ("c divisible by 17 / 19 (extended sieve)", lambda p, c: (c % 17 == 0, c % 19 == 0)),
]


def rank_of(cands, p, q):
    """Position of q among the candidates after p (1 = the very first)."""
    return bisect_right(cands, q) - bisect_right(cands, p)


def train_rank_model(feature, train, cands):
    """Feature value -> most frequent rank of the next prime (the smaller one on a tie)."""
    stats = defaultdict(Counter)
    for prev, p, q in train:
        stats[feature(p, prev)][rank_of(cands, p, q)] += 1
    return {key: max(ranks, key=lambda r: (ranks[r], -r)) for key, ranks in stats.items()}


def train_candidate_model(feature, b):
    """Returns prob(p, c): sieve random model × learned factor of the feature value."""
    prime, expected = Counter(), Counter()
    for _, p, q in b.train:
        for c in b.cands[bisect_right(b.cands, p):bisect_right(b.cands, q)]:    # every one up to and including q
            key = feature(p, c)
            expected[key] += sieve_model(c, b.base)
            prime[key] += c == q

    def prob(p, c):
        key = feature(p, c)
        return min((prime[key] + 0.5) / (expected[key] + 0.5) * sieve_model(c, b.base), 0.999)
    return prob


def predict_candidate(prob, cands, p, depth=20):
    """The candidate with the highest chance of being the first prime after p."""
    best, best_score, survive = None, -1.0, 1.0
    i = bisect_right(cands, p)
    for c in cands[i:i + depth]:
        pc = prob(p, c)
        if survive * pc > best_score:
            best, best_score = c, survive * pc
        survive *= 1 - pc
    return best


def candidate_hits(prob, b):
    return sum(predict_candidate(prob, b.cands, p) == q for _, p, q in b.test)


def candidate_bits(prob, b):
    """Bits per candidate in the test range when the model predicts every candidate (as when packing)."""
    p, probs = b.test[0][1], []
    for c, bit in zip(b.test_cands, b.test_bits):
        probs.append(prob(p, c))
        if bit:
            p = c
    return code_length(b.test_bits, probs) / len(b.test_bits)


def print_eval_header(label="feature"):
    print("  {:<42} {:>7} {:>8}  {:<10} {:>8} {:>8}".format(label, "hits", "vs wheel", "", "bits", "vs ref"))


def evaluate(experiment, name, prob, b):
    """One probability model on both metrics: hits and bits per candidate."""
    rate = candidate_hits(prob, b) / len(b.test)
    bits = candidate_bits(prob, b)
    v_hits = verdict_hits(rate, b.baseline, len(b.test))
    v_bits = verdict_lower(bits, b.ref_bits, 0.005)
    print("  {:<42} {:>7.2%} {:>+8.2%}  {:<10} {:>8.4f} {:>+8.2%}  {}".format(
        name, rate, rate - b.baseline, v_hits, bits, bits / b.ref_bits - 1, v_bits))
    record(experiment, name, "hits", "{:.2%}".format(rate), wheel_ref(b), v_hits)
    record(experiment, name, "bits/candidate", "{:.4f}".format(bits), bits_ref(b), v_bits)
    return rate, bits


def cmd_predict(args):
    b = bench(args.limit, args.k)
    print_bench(b)

    print("A) Wheel: q = first candidate after p that no divisor removes")
    print("{:<20} {:>10} {:>16} {:>14}".format("divisors", "hits", "Ø candidates", "Ø gap q-p"))
    for k in range(1, len(b.base) + 1):
        cands = set_bits(candidate_field(b.limit, b.base[:k]))
        ranks = [rank_of(cands, p, q) for _, p, q in b.test]
        print("{:<20} {:>9.1%} {:>16.2f} {:>14.2f}".format(
            ",".join(map(str, b.base[:k])), ranks.count(1) / len(b.test), sum(ranks) / len(b.test),
            sum(q - p for _, p, q in b.test) / len(b.test)))

    print("\nB) Rank model: feature of p -> at which position among the wheel candidates is q?")
    print("  {:<42} {:>7} {:>8}".format("feature", "hits", "vs wheel"))
    for name, feature in RANK_FEATURES:
        model = train_rank_model(feature, b.train, b.cands)
        hits = sum(model.get(feature(p, prev), 1) == rank_of(b.cands, p, q) for prev, p, q in b.test)
        report("Features: rank model", name, hits, b)

    print("\nC) Candidate model: feature of c -> how likely is candidate c prime?")
    print_eval_header()
    for name, feature in CANDIDATE_FEATURES:
        evaluate("Features: candidate model", name, train_candidate_model(feature, b), b)

    mean_log = sum(math.log(p) for _, p, _ in b.test) / len(b.test)
    print("\nFor comparison: mean gap by the prime number theorem ~ ln(p) = {:.2f}".format(mean_log))
    print("Hits: 'better'/'worse' only beyond 2 standard errors (±{:.2%}); bits: beyond ±0.5 %.".format(
        2 * math.sqrt(2 * b.baseline * (1 - b.baseline) / len(b.test))))
    print("-> Excluding works perfectly; 'predicting' remains a statement of probability.")


# ---------------------------------------------------------------------------
# Ramanujan sums and filter bank
# ---------------------------------------------------------------------------

def mobius(n):
    result, p = 1, 2
    while p * p <= n:
        if n % p == 0:
            n //= p
            if n % p == 0:
                return 0
            result = -result
        p += 1
    return -result if n > 1 else result


def euler_phi(n):
    result, m, p = n, n, 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            result -= result // p
        p += 1
    if m > 1:
        result -= result // m
    return result


def ramanujan_sum(q, n):
    """c_q(n) = sum of cos(2πkn/q) over k coprime to q = Σ_{d | gcd(n,q)} μ(q/d)·d."""
    g = math.gcd(n, q)
    return sum(mobius(q // d) * d for d in range(1, g + 1) if g % d == 0)


def divisor_masks(limit, moduli):
    """masks[n]: bit i is set if moduli[i] divides n."""
    masks = [0] * (limit + 1)
    for i, p in enumerate(moduli):
        bit = 1 << i
        for m in range(p, limit + 1, p):
            masks[m] |= bit
    return masks


def hardy_score(Q, moduli):
    """Truncated Ramanujan expansion S_Q(n) = Σ_{q≤Q} μ(q)/φ(q)·c_q(n) as a function of the divisor mask.

    For squarefree q, μ(q)/φ(q)·c_q(n) = Π_{p|q} (−1 if p|n, else 1/(p−1)).
    """
    index = {p: i for i, p in enumerate(moduli)}
    terms = [[index[p] for p in moduli if q % p == 0] for q in range(1, Q + 1) if mobius(q) != 0]
    relevant = (1 << sum(p <= Q for p in moduli)) - 1
    cache = {}

    def score(mask):
        key = mask & relevant
        if key not in cache:
            total = 0.0
            for idx in terms:
                prod = 1.0
                for i in idx:
                    prod *= -1.0 if key >> i & 1 else 1.0 / (moduli[i] - 1)
                total += prod
            cache[key] = total
        return cache[key]
    return score


def cmd_ramanujan(args):
    b = bench(args.limit, args.k)
    print_bench(b)
    N = b.limit // 2
    data = [p for p in b.primes if p <= N]
    print("1) Ramanujan filter bank on the sequence of primes up to {}: share of every period q".format(N))
    print("   measured a_q = Σ ln(p)·c_q(p) / (φ(q)·N),  theory (Hardy 1921): μ(q)/φ(q)\n")
    print("{:>5} {:>12} {:>12}".format("q", "theory", "measured"))
    for q in range(1, 13):
        measured = sum(math.log(p) * ramanujan_sum(q, p) for p in data) / (euler_phi(q) * N)
        print("{:>5} {:>12.4f} {:>12.4f}".format(q, mobius(q) / euler_phi(q), measured))
    print("-> The filter bank finds exactly Hardy's coefficients: the periods of the primes are known.")

    moduli = small_primes(max(args.q))
    masks = divisor_masks(b.limit, moduli)
    check = hardy_score(30, moduli)
    ok = all(abs(check(masks[n]) - sum(mobius(q) / euler_phi(q) * ramanujan_sum(q, n) for q in range(1, 31))) < 1e-9
             for n in range(2, 300))
    print("\n   Control: product formula = direct sum of the c_q(n) (Q = 30, n < 300): {}".format("ok" if ok else "FAILED"))

    n = len(b.test)
    print("\n2) Prediction with the truncated expansion S_Q(c) = Σ_{q≤Q} μ(q)/φ(q)·c_q(c)")
    print("   theory:      π(c) = S_Q(c) / ln(c), no training at all")
    print("   calibrated:  the candidate model learns π for every value of S_Q(c)")
    print("   sieve to Q:  the candidate model only knows 'divisible by a prime up to Q'\n")
    print("{:>5}  {:>27}  {:>27}  {:>27}".format("Q", "theory", "calibrated", "sieve to Q"))
    print("{:>5}  {}".format("", "  ".join("{:>27}".format("hits          bits/cand.") for _ in range(3))))
    for Q in args.q:
        score = hardy_score(Q, moduli)
        extra = sum(1 << i for i, p in enumerate(moduli) if b.base[-1] < p <= Q)
        models = [
            lambda p, c: min(max(score(masks[c]) / math.log(c), 1e-9), 0.999),
            train_candidate_model(lambda p, c: round(score(masks[c]), 9), b),
            train_candidate_model(lambda p, c: bool(masks[c] & extra), b),
        ]
        rates = [candidate_hits(m, b) / n for m in models]
        bits = [candidate_bits(m, b) for m in models]
        print("{:>5}  {}".format(Q, "  ".join(
            "{:>7.2%} ({:+.2%}) {:>7.4f}".format(r, r - b.baseline, x) for r, x in zip(rates, bits))))
        sieve_ref = "sieve to {}: {:.2%}".format(Q, rates[2])
        sieve_bits = "sieve to {}: {:.4f}".format(Q, bits[2])
        for i, name in enumerate(("theory S_Q/ln c, Q = {}".format(Q), "calibrated, Q = {}".format(Q))):
            record("Ramanujan filter bank", name, "hits", "{:.2%}".format(rates[i]), sieve_ref,
                   verdict_hits(rates[i], rates[2], n))
            record("Ramanujan filter bank", name, "bits/candidate", "{:.4f}".format(bits[i]), sieve_bits,
                   verdict_lower(bits[i], bits[2], 0.005))
        record("Ramanujan filter bank", "sieve to Q = {}".format(Q), "hits", "{:.2%}".format(rates[2]),
               wheel_ref(b), verdict_hits(rates[2], b.baseline, n))
        record("Ramanujan filter bank", "sieve to Q = {}".format(Q), "bits/candidate", "{:.4f}".format(bits[2]),
               bits_ref(b), verdict_lower(bits[2], b.ref_bits, 0.005))
    print("\n   Hit differences below ±{:.2%} are noise.".format(
        2 * math.sqrt(2 * b.baseline * (1 - b.baseline) / n)))
    print("   In the comparison table, theory and calibrated are judged against 'sieve to Q' (same information).")
    print("-> Taking every squarefree q made of primes ≤ P instead of q ≤ Q, the sum becomes exactly")
    print("   0 for divisible n and Π p/(p−1) otherwise: the Ramanujan expansion is the sieve in Fourier form.")


# ---------------------------------------------------------------------------
# 1 Compression test
# ---------------------------------------------------------------------------

def pack_bits(bits):
    out = bytearray((len(bits) + 7) // 8)
    for i, bit in enumerate(bits):
        if bit:
            out[i >> 3] |= 1 << (i & 7)
    return bytes(out)


def entropy_bits(p):
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def adaptive_probs(bits, contexts):
    """P(prime) per context, learned from the past only (Krichevsky-Trofimov estimator)."""
    ones, total, probs = Counter(), Counter(), []
    for bit, ctx in zip(bits, contexts):
        probs.append((ones[ctx] + 0.5) / (total[ctx] + 1))
        ones[ctx] += bit
        total[ctx] += 1
    return probs


def history_contexts(bits, depth):
    """Context = the last depth bits (prime / not prime of the preceding candidates)."""
    ctx, mask, out = 0, (1 << depth) - 1, []
    for bit in bits:
        out.append(ctx)
        ctx = ((ctx << 1) | bit) & mask
    return out


def cmd_compress(args):
    b = bench(args.limit, args.k)
    print_bench(b)
    cands, bits, ref = b.test_cands, b.test_bits, b.ref_bits
    n = len(bits)
    packed = pack_bits(bits)
    print("Prime bits of the {} wheel candidates in the test range ({:.2%} prime).".format(n, sum(bits) / n))
    print("A method that finds a pattern needs fewer bits than the sieve random model.\n")
    rows = [
        ("constant rate (Bernoulli entropy)", entropy_bits(sum(bits) / n)),
        ("zlib -9", 8 * len(zlib.compress(packed, 9)) / n),
        ("bz2 -9", 8 * len(bz2.compress(packed, 9)) / n),
        ("lzma extreme", 8 * len(lzma.compress(packed, preset=9 | lzma.PRESET_EXTREME)) / n),
    ]
    contexts = [
        ("context: last 8 candidates", history_contexts(bits, 8)),
        ("context: last 16 candidates", history_contexts(bits, 16)),
        ("context: lowest 4 bits of c", [c & 0b1111 for c in cands]),
        ("context: Hamming weight of c", [popcount(c) for c in cands]),
        ("context: c divisible by 17/19 (positive control)", [(c % 17 == 0, c % 19 == 0) for c in cands]),
    ]
    for name, ctx in contexts:
        rows.append((name, code_length(bits, adaptive_probs(bits, ctx)) / n))

    print("  {:<50} {:>14} {:>9}".format("method", "bits/candidate", "vs ref"))
    print("  {:<50} {:>14.4f} {:>9}".format("sieve random model π = W/ln c (reference)", ref, ""))
    for name, value in rows:
        verdict = verdict_lower(value, ref, 0.005)
        print("  {:<50} {:>14.4f} {:>+8.2%}   {}".format(name, value, value / ref - 1, verdict))
        record("1 Compression", name, "bits/candidate", "{:.4f}".format(value), bits_ref(b), verdict)

    raw = [int(m in b.primeset) for m in range(b.test[0][1] + 1, b.limit + 1)]
    raw_lzma = 8 * len(lzma.compress(pack_bits(raw), preset=9 | lzma.PRESET_EXTREME)) / len(raw)
    print("\nPositive control on the raw bit field of all {} numbers (even ones included): bits per number".format(
        len(raw)))
    print("  no knowledge {:.4f}   lzma {:.4f}   sieve model {:.4f}".format(
        entropy_bits(sum(raw) / len(raw)), raw_lzma, ref * n / len(raw)))
    print("\n'better'/'worse' beyond ±0.5 % against the reference.")
    print("-> Compressors find the wheel in the raw field, but no pattern beyond the sieve.")


# ---------------------------------------------------------------------------
# 2 Lemke Oliver-Soundararajan bias
# ---------------------------------------------------------------------------

BIAS_FEATURES = [
    ("last digits (p mod 10, c mod 10)", lambda p, c: (p % 10, c % 10)),
    ("lowest 3 bits (p mod 8, c mod 8)", lambda p, c: (p & 0b111, c & 0b111)),
    ("distance c − p", lambda p, c: c - p),
]


def random_primes(limit, divisors, seed=1):
    """Sieve random model: wheel candidates are 'prime' independently, with probability W/ln c."""
    rng = random.Random(seed)
    weight = sieve_weight(divisors)
    return [c for c in set_bits(candidate_field(limit, divisors))
            if c in divisors or rng.random() < weight / math.log(c)]


def consecutive_pairs(primes, minimum):
    return [(p, q) for p, q in zip(primes, primes[1:]) if p > minimum]


def transition_shares(pairs, mod):
    """Row shares: shares[a][r] = share of the pairs with p ≡ a whose successor is q ≡ r (mod mod)."""
    counts = defaultdict(Counter)
    for p, q in pairs:
        counts[p % mod][q % mod] += 1
    shares = {a: {r: row[r] / sum(row.values()) for r in row} for a, row in counts.items()}
    sizes = {a: sum(row.values()) for a, row in counts.items()}
    return shares, sizes


def print_matrix(title, classes, cell):
    print("  {:>14}{}".format(title, "".join("{:>8}".format(r) for r in classes)))
    for a in classes:
        print("  {:>14}{}".format(a, "".join(cell(a, r) for r in classes)))


def cmd_bias(args):
    b = bench(args.limit, args.k)
    print_bench(b)
    print("Lemke Oliver & Soundararajan (2016): in which residue class does the next prime q lie?")
    print("Compared with the sieve random model: same candidates, same density, but independent.\n")
    model = random_primes(b.limit, tuple(small_primes(97)))
    for mod, minimum, label in ((10, 5, "last digit (mod 10)"), (8, 2, "lowest 3 bits (mod 8)")):
        classes = [r for r in range(mod) if math.gcd(r, mod) == 1]
        real, sizes = transition_shares(consecutive_pairs(b.primes, minimum), mod)
        fake, _ = transition_shares(consecutive_pairs(model, minimum), mod)
        print("{} of consecutive primes up to {} (row p, column q):".format(label, b.limit))
        print_matrix("real mod {}".format(mod), classes, lambda a, r: "{:>8.1%}".format(real[a].get(r, 0)))
        print_matrix("model to 97", classes, lambda a, r: "{:>8.1%}".format(fake[a].get(r, 0)))
        z = {(a, r): (real[a].get(r, 0) - fake[a].get(r, 0)) /
             math.sqrt(2 * max(real[a].get(r, 0), 1e-9) * (1 - real[a].get(r, 0)) / sizes[a])
             for a in classes for r in classes}
        print_matrix("dev. in σ", classes, lambda a, r: "{:>+8.1f}".format(z[(a, r)]))
        worst = max(z.values(), key=abs)
        same = sum(real[a].get(a, 0) for a in classes) / len(classes)
        print("  same residue class: real {:.2%}, model {:.2%}, uniform {:.2%}; largest deviation {:+.1f} σ\n".format(
            same, sum(fake[a].get(a, 0) for a in classes) / len(classes), 1 / len(classes), worst))
        verdict = "structure beyond the model" if abs(worst) > 4 else "explained by the model"
        record("2 Residue class bias", "transitions mod {}: real against sieve model to 97".format(mod), "max. dev.",
               "{:+.1f} σ".format(worst), "noise: < 4 σ", verdict)
    print("  (16 cells per table, so only a deviation above 4 σ counts as real.)\n")

    print("Prediction with the residue classes as a feature (candidate model, same bench):")
    print_eval_header()
    for name, feature in BIAS_FEATURES:
        evaluate("2 Residue class bias", name, train_candidate_model(feature, b), b)
    print("\n-> The bias is real (about 15 % instead of 25 %), but it already follows from the sieve: the")
    print("   independent sieve random model produces the same table. 'distance c − p' carries, through")
    print("   Hardy-Littlewood, only a tiny remainder of sieve knowledge (c − p ≡ 0 mod 17 ⇒ c not divisible")
    print("   by 17) -- not measurable.")


# ---------------------------------------------------------------------------
# 3 Riemann zeros
# ---------------------------------------------------------------------------

def rs_theta(t):
    return t / 2 * math.log(t / (2 * math.pi)) - t / 2 - math.pi / 8 + 1 / (48 * t) + 7 / (5760 * t ** 3)


def rs_z(t):
    """Riemann-Siegel Z function: real, same zeros as ζ(1/2 + it)."""
    a = math.sqrt(t / (2 * math.pi))
    N = int(a)
    theta = rs_theta(t)
    main = sum(math.cos(theta - t * math.log(n)) / math.sqrt(n) for n in range(1, N + 1))
    frac = a - N
    if abs(math.cos(2 * math.pi * frac)) < 1e-12:
        frac += 1e-9
    c0 = math.cos(2 * math.pi * (frac * frac - frac - 1 / 16)) / math.cos(2 * math.pi * frac)
    return 2 * main + (-1) ** (N - 1) * c0 / math.sqrt(a)


@functools.lru_cache(maxsize=None)
def zeta_zeros(count, step=0.02):
    """The first count zeros (imaginary parts) from sign changes of Z(t) plus bisection.

    Returns (zeros, search height T, number of all zeros found below T).
    """
    height = 50.0
    while rs_theta(height) / math.pi + 1 < count + 3:
        height *= 1.2
    zeros, t, z = [], 10.0, rs_z(10.0)
    while t < height:
        t2 = t + step
        z2 = rs_z(t2)
        if z * z2 < 0:
            lo, hi, zlo = t, t2, z
            for _ in range(40):
                mid = (lo + hi) / 2
                zmid = rs_z(mid)
                if zlo * zmid <= 0:
                    hi = mid
                else:
                    lo, zlo = mid, zmid
            zeros.append((lo + hi) / 2)
        t, z = t2, z2
    return tuple(zeros[:count]), height, len(zeros)


def psi_explicit(x, zeros):
    """Riemann's explicit formula: ψ(x) = x − Σ_ρ x^ρ/ρ − ln(2π) − ½·ln(1 − x^−2), zeros in pairs."""
    lx = math.log(x)
    oscillation = sum((0.5 * math.cos(g * lx) + g * math.sin(g * lx)) / (0.25 + g * g) for g in zeros)
    return x - 2 * math.sqrt(x) * oscillation - math.log(2 * math.pi) - 0.5 * math.log(1 - x ** -2)


def prime_powers(primes, limit):
    """(p^k, ln p) for every prime power ≤ limit, ascending: the jumps of ψ."""
    out = []
    for p in primes:
        m = p
        while m <= limit:
            out.append((m, math.log(p)))
            m *= p
    out.sort()
    return out


def cmd_zeta(args):
    b = bench(args.limit, args.k)
    print_bench(b)
    Ks = sorted(args.zeros)
    zeros, height, found = zeta_zeros(max(Ks))
    print("1) {} zeros from the Riemann-Siegel Z function (standard library only)".format(len(zeros)))
    print("   first: {}".format(", ".join("{:.4f}".format(g) for g in zeros[:5])))
    print("   control Riemann-von Mangoldt: below t = {:.1f} expected ≈ {:.1f}, found {}".format(
        height, rs_theta(height) / math.pi + 1, found))
    try:
        import mpmath
        deviation = max(abs(float(mpmath.zetazero(i).imag) - zeros[i - 1]) for i in range(1, 6))
        print("   control against mpmath (first 5): max. deviation {:.4f}".format(deviation))
    except ImportError:
        pass

    print("\n2) Peak test: −Σ cos(γ·ln x) over K zeros peaks at prime powers.")
    print("   The strongest peaks among x = 2..100 compared with the actual prime powers:\n")
    powers = {m for m, _ in prime_powers(small_primes(100), 100)}
    chance = len(powers) / 99
    print("  {:>6} {:>12} {:>18}".format("K", "recognised", "resolution at 100"))
    for K in Ks:
        gs = zeros[:K]
        score = {x: -sum(math.cos(g * math.log(x)) for g in gs) for x in range(2, 101)}
        top = sorted(score, key=score.get, reverse=True)[:len(powers)]
        hit = len(powers & set(top))
        se = math.sqrt(chance * (1 - chance) / len(powers))
        verdict = "better" if hit / len(powers) > chance + 2 * se else "≈ chance"
        print("  {:>6} {:>9}/{:<2} {:>18.2f}".format(K, hit, len(powers), 2 * math.pi * 100 / gs[-1]))
        record("3 Riemann zeros", "peaks K = {}: prime powers ≤ 100".format(K), "recognised",
               "{}/{}".format(hit, len(powers)), "chance: {:.0%}".format(chance), verdict)
    print("   To separate single numbers at x one needs γ > 2πx -- at x = 10^6 that is millions of zeros.")

    W = args.window
    edges = list(range(b.test[0][1], b.limit + 1, W))
    powers_list = prime_powers(b.primes, b.limit)
    positions = [m for m, _ in powers_list]
    prefix = [0.0] + list(accumulate(w for _, w in powers_list))

    def psi_true(x):
        return prefix[bisect_right(positions, x)]

    true = [psi_true(e2) - psi_true(e1) for e1, e2 in zip(edges, edges[1:])]
    print("\n3) Counting in {} windows of {} numbers in the test range: error of ψ(window) against the truth".format(
        len(true), W))
    print("  {:>6} {:>12} {:>16}".format("K", "RMS error", "explained (R²)"))
    ref = None
    for K in [0] + Ks:
        gs = zeros[:K]
        pred = [psi_explicit(e2, gs) - psi_explicit(e1, gs) for e1, e2 in zip(edges, edges[1:])]
        rms = math.sqrt(sum((x - y) ** 2 for x, y in zip(pred, true)) / len(true))
        if ref is None:
            ref = rms
            print("  {:>6} {:>12.1f} {:>16}   (prime number theorem ψ ≈ x only)".format(K, rms, "-"))
            continue
        verdict = verdict_lower(rms, ref, 0.10)
        print("  {:>6} {:>12.1f} {:>15.1%}   {}".format(K, rms, 1 - (rms / ref) ** 2, verdict))
        record("3 Riemann zeros", "K = {}: ψ in windows of {}".format(K, W), "RMS error",
               "{:.1f}".format(rms), "PNT: {:.1f}".format(ref), verdict)
    print("   'better' from 10 % less error than the prime number theorem.")

    K = min(100, max(Ks))
    gs = zeros[:K]
    cache = {}

    def density(p, c):
        if c not in cache:
            lc = math.log(c)
            local = 1 - 2 / math.sqrt(c) * sum(math.cos(g * lc) for g in gs)
            cache[c] = min(max(sieve_model(c, b.base) * local, 1e-9), 0.999)
        return cache[c]

    print("\n4) Next prime with the local density from {} zeros as π(c):".format(K))
    print_eval_header("model")
    evaluate("3 Riemann zeros", "density from {} zeros".format(K), density, b)
    print("-> The zeros describe the density on large scales, not the single next prime.")


# ---------------------------------------------------------------------------
# 4 Polynomials and Bateman-Horn
# ---------------------------------------------------------------------------

POLYNOMIALS = [                            # f(n) = a·n² + b·n + c
    ("n² + n + 41 (Euler)", (1, 1, 41)),
    ("4n² − 2n + 41 (Ulam diagonal)", (4, -2, 41)),
    ("2n² + 29", (2, 0, 29)),
    ("n² + n + 17", (1, 1, 17)),
    ("n² + 1", (1, 0, 1)),
    ("4n² + 1", (4, 0, 1)),
    ("n² + n + 1", (1, 1, 1)),
    ("n² + 2", (1, 0, 2)),
    ("n² + 3", (1, 0, 3)),
    ("n² + 7", (1, 0, 7)),
    ("n² − 2", (1, 0, -2)),
    ("n² + n + 2 (always even)", (1, 1, 2)),
]


def poly_roots_mod(f, p):
    """ω_f(p): number of n mod p with f(n) ≡ 0 -- how many residue classes the polynomial 'loses'."""
    a, b, c = f
    if p == 2 or a % p == 0:
        return sum((a * n * n + b * n + c) % p == 0 for n in range(p))
    d = (b * b - 4 * a * c) % p
    if d == 0:
        return 1
    return 2 if pow(d, (p - 1) // 2, p) == 1 else 0


def bateman_horn_constant(f, primes):
    """C_f = Π_p (1 − ω_f(p)/p) / (1 − 1/p)."""
    C = 1.0
    for p in primes:
        C *= (1 - poly_roots_mod(f, p) / p) / (1 - 1 / p)
    return C


def cmd_poly(args):
    N = args.n
    primes = set_bits(prime_field(args.bound))
    print("Bateman-Horn: expected primes among f(1), ..., f(N) = C_f · Σ 1/ln f(n)")
    print("C_f = Π_p (1 − ω_f(p)/p)/(1 − 1/p), ω_f(p) = roots of f mod p, product over p ≤ {}, N = {}".format(
        args.bound, N))
    print("Counted with Miller-Rabin (experiment 6).\n")
    print("  {:<32} {:>7} {:>9} {:>14} {:>8} {:>12} {:>8}".format(
        "polynomial", "C_f", "measured", "Bateman-Horn", "error", "naive 1/ln", "error"))
    errors_bh, errors_naive = [], []
    for name, f in POLYNOMIALS:
        a, b, c = f
        values = [v for v in (a * n * n + b * n + c for n in range(1, N + 1)) if v >= 2]
        measured = sum(miller_rabin(v) for v in values)
        naive = sum(1 / math.log(v) for v in values)
        C = bateman_horn_constant(f, primes)
        predicted = C * naive
        if measured:
            e_bh, e_naive = abs(predicted - measured) / measured, abs(naive - measured) / measured
            errors_bh.append(e_bh)
            errors_naive.append(e_naive)
            errs = "{:>8.2%} {:>12.0f} {:>8.1%}".format(e_bh, naive, e_naive)
        else:
            errs = "{:>8} {:>12.0f} {:>8}".format("exact", naive, "-")
        print("  {:<32} {:>7.3f} {:>9} {:>14.0f} {}".format(name, C, measured, predicted, errs))
    mean_bh, mean_naive = sum(errors_bh) / len(errors_bh), sum(errors_naive) / len(errors_naive)
    print("\n  mean relative error: Bateman-Horn {:.2%}, naive {:.1%}".format(mean_bh, mean_naive))
    record("4 Polynomials", "Bateman-Horn (residue class constant C_f)", "rel. error", "{:.2%}".format(mean_bh),
           "naive 1/ln: {:.1%}".format(mean_naive), verdict_lower(mean_bh, mean_naive, 0.10))
    print("-> The density on curves can be predicted well -- from the residue classes mod p alone.")


# ---------------------------------------------------------------------------
# 5 Learning: bits against RNS
# ---------------------------------------------------------------------------

def bit_features(c, width):
    return [1 + j for j in range(width) if c >> j & 1]


def bitpair_features(c, width):
    on = [j for j in range(width) if c >> j & 1]
    return [1 + j for j in on] + [1000 + i * 64 + j for k, i in enumerate(on) for j in on[k + 1:]]


def rns_features(c, moduli):
    return [100000 + p * 1000 + c % p for p in moduli]


def logistic(z):
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def train_logistic(samples, epochs, lr=0.2, seed=1):
    """Logistic regression with AdaGrad. samples: (active features, fixed offset, label)."""
    w, g2 = defaultdict(float), defaultdict(float)
    order = list(range(len(samples)))
    rng = random.Random(seed)
    for _ in range(epochs):
        rng.shuffle(order)
        for i in order:
            feats, offset, y = samples[i]
            g = logistic(offset + sum(w[f] for f in feats)) - y
            for f in feats:
                g2[f] += g * g
                w[f] -= lr * g / math.sqrt(g2[f])
    return w


def cmd_learn(args):
    b = bench(args.limit, args.k)
    print_bench(b)
    width = b.limit.bit_length()

    def offset(c):                         # every model starts from the sieve random model
        p0 = sieve_model(c, b.base)
        return math.log(p0 / (1 - p0))

    feature_sets = [
        ("sieve random model only (+ bias)", lambda c: []),
        ("bits of c", lambda c: bit_features(c, width)),
        ("bits + every pair of bits", lambda c: bitpair_features(c, width)),
        ("RNS 2..13 (one-hot)", lambda c: rns_features(c, (2, 3, 5, 7, 11, 13))),
        ("RNS 17..31 (one-hot)", lambda c: rns_features(c, (17, 19, 23, 29, 31))),
        ("bits + RNS 17..31", lambda c: bit_features(c, width) + rns_features(c, (17, 19, 23, 29, 31))),
    ]
    train_c = [c for c in b.cands if 1000 <= c <= b.test[0][1]]
    print("Logistic regression on {} training candidates, tested on {} candidates ({} epochs).".format(
        len(train_c), len(b.test_cands), args.epochs))
    print("Every model starts from the sieve random model and only learns corrections from its features.\n")
    print_eval_header("input")
    for name, feats in feature_sets:
        samples = [([0] + feats(c), offset(c), int(c in b.primeset)) for c in train_c]
        w = train_logistic(samples, args.epochs)
        probs = {c: logistic(offset(c) + sum(w.get(f, 0.0) for f in [0] + feats(c))) for c in b.test_cands}
        evaluate("5 Learning: bits against RNS", name, lambda p, c: probs[c], b)
    print("\n-> From the bits the model learns nothing; from the residue vector it learns the sieve (cf. 'sieve to 31').")


# ---------------------------------------------------------------------------
# 6 Next prime: sieve + Miller-Rabin
# ---------------------------------------------------------------------------

def next_prime(n, sieve_primes):
    """Next prime > n: sieve a segment as a bit field, Miller-Rabin only for the survivors."""
    seg = max(64, 2 * int(n.bit_length() * math.log(2)))
    start, tests = n + 1, 0
    while True:
        field = (1 << seg) - 1             # bit t <-> number start + t
        for p in sieve_primes:
            if p >= start:
                break
            field &= ~stride_mask(p, (-start) % p, seg)
        for t in set_bits(field):
            tests += 1
            if miller_rabin(start + t):
                return start + t, tests
        start += seg


SIEVE_BOUNDS = (2, 13, 1000, 10000)
MAGNITUDES = [("10^6", 10 ** 6), ("2^64", 2 ** 64), ("10^30", 10 ** 30), ("2^127", 2 ** 127),
              ("10^50", 10 ** 50), ("2^256", 2 ** 256), ("10^100", 10 ** 100)]


def cmd_nextprime(args):
    b = bench(args.limit, args.k)
    wrong = sum(miller_rabin(n) != (n in b.primeset) for n in range(b.limit + 1))
    print("1) Miller-Rabin against the exact bit field, every n ≤ {}: {} errors".format(b.limit, wrong))
    record("6 Sieve + Miller-Rabin", "Miller-Rabin against bit field to {}".format(b.limit), "errors", str(wrong),
           "0", "correct" if wrong == 0 else "FAILED")
    print("   561 = 3·11·17: Fermat test 2^560 mod 561 = {} (says 'prime'), Miller-Rabin: {}".format(
        pow(2, 560, 561), "prime" if miller_rabin(561) else "composite"))
    print("   2^127 − 1 (Mersenne): {},  2^128 + 1 (Fermat number): {}".format(
        "prime" if miller_rabin(2 ** 127 - 1) else "composite",
        "prime" if miller_rabin(2 ** 128 + 1) else "composite"))
    q, _ = next_prime(10 ** 30, small_primes(1000))
    d = (q - 1) >> ((q - 1) & -(q - 1)).bit_length() - 1
    print("   next prime after 10^30 = {}".format(q))
    print("   pow(a, d, n) walks the {} bits of d: {} squarings + {} multiplications per base".format(
        d.bit_length(), d.bit_length() - 1, popcount(d) - 1))

    print("\n2) Ø Miller-Rabin tests up to the next prime ({} searches in a row per magnitude)".format(args.runs))
    print("   'sieve ≤ 13' is the bench's wheel ('Ø candidates' in predict).\n")
    sieves = {B: small_primes(B) for B in SIEVE_BOUNDS}
    print("  {:<8} {:>7}{} {:>12}".format(
        "n ≈", "ln n", "".join("{:>15}".format("sieve ≤ {}".format(B)) for B in SIEVE_BOUNDS), "ms/search"))
    for label, start in MAGNITUDES:
        averages, elapsed = [], 0.0
        for B in SIEVE_BOUNDS:
            n, tests = start, 0
            t0 = time.perf_counter()
            for _ in range(args.runs):
                n, used = next_prime(n, sieves[B])
                tests += used
            elapsed = (time.perf_counter() - t0) * 1000 / args.runs
            averages.append(tests / args.runs)
        print("  {:<8} {:>7.1f}{} {:>12.2f}".format(
            label, start.bit_length() * math.log(2), "".join("{:>15.2f}".format(a) for a in averages), elapsed))
        if label in ("10^6", "2^127", "10^100"):
            record("6 Sieve + Miller-Rabin", "sieve ≤ 10000 + Miller-Rabin, n ≈ {}".format(label), "Ø MR tests",
                   "{:.2f}".format(averages[-1]), "wheel up to 13: {:.2f}".format(averages[1]),
                   verdict_lower(averages[-1], averages[1], 0.05))
    print("\n-> The binary representation pays off for testing fast, not for predicting.")


# ---------------------------------------------------------------------------
# 7 Unexplored ranges: binary patterns far beyond 10^6
# ---------------------------------------------------------------------------

WINDOW_PROPERTIES = [                      # (name, short name for the table, property of c)
    ("all primes (prime number theorem in the window)", "all", lambda c: True),
    ("even Hamming weight (Mauduit-Rivat)", "TM even", lambda c: popcount(c) % 2 == 0),
    ("Hamming weight ≡ 0 mod 3", "wt≡0(3)", lambda c: popcount(c) % 3 == 0),
    ("no '11' in the lowest 16 bits", "no 11", lambda c: (c & 0xFFFF) & ((c & 0xFFFF) >> 1) == 0),
    ("bits 3,7,11,15 = 1,0,1,0 (Bourgain)", "Bourgain", lambda c: (c >> 3) & 0x1111 == 0x0101),
]


def parse_height(text):
    """'2^64' or '10^50' or a plain number."""
    base, _, exponent = text.partition("^")
    return int(base) ** int(exponent) if exponent else int(base)


@functools.lru_cache(maxsize=None)
def primorial(bound):
    return math.prod(small_primes(bound))


def window_survivors(start, width, sieve_primes):
    """Every number in [start, start + width) that survives the sieve with sieve_primes (bit field)."""
    field = (1 << width) - 1
    for p in sieve_primes:
        field &= ~stride_mask(p, (-start) % p, width)
    return [start + t for t in set_bits(field)]


def z_score(observed, expected, variance):
    if variance <= 0:
        return 0.0 if abs(observed - expected) < 1e-9 else math.inf
    return (observed - expected) / math.sqrt(variance)


def verdict_z(z):
    return "structure beyond the model" if abs(z) > 4 else "explained by the model"


def model_test(elements, bound, weight):
    """Primes among elements against the sieve random model: expectation Σ π, variance Σ π(1−π).

    An element survives the sieve if gcd(s, primorial(bound)) = 1; it is then prime with π = W/ln s.
    """
    M = primorial(bound)
    observed = expected = variance = 0.0
    survivors = 0
    for s in elements:
        if math.gcd(s, M) != 1:
            continue                       # certainly composite (s > bound)
        pi = min(weight / math.log(s), 0.999)
        expected += pi
        variance += pi * (1 - pi)
        survivors += 1
        observed += miller_rabin(s)
    return observed, expected, z_score(observed, expected, variance), survivors


def random_weight(bits, ones, rng):
    """Random odd number with exactly bits digits and exactly ones 1-bits."""
    value = (1 << (bits - 1)) | 1
    for j in rng.sample(range(1, bits - 1), ones - 2):
        value |= 1 << j
    return value


def random_fibbinary(bits, rng):
    """Random odd number with exactly bits digits and no two adjacent 1-bits."""
    value, prev = 1, 1
    for _ in range(bits - 3):
        bit = 0 if prev else rng.getrandbits(1)
        value, prev = (value << 1) | bit, bit
    return (value << 2) | 1                # ...01 at the end


def random_palindrome(bits, rng):
    """Random binary palindrome with exactly bits digits."""
    half = (bits + 1) // 2
    head = "1" + format(rng.getrandbits(half - 1), "0{}b".format(half - 1))
    return int(head + head[-2::-1] if bits % 2 else head + head[::-1], 2)


def min_bits(bound):
    """Smallest bit length with u = ln s / ln bound ≥ 4. Below it the density of sieve-free numbers
    departs noticeably from the Mertens product (Buchstab function) and the sieve random model
    becomes inaccurate."""
    return math.ceil(4 * math.log2(bound))


def thin_sets(args, rng):
    h, n, a0 = args.bits, args.samples, min_bits(args.bound)
    return [
        ("weight 3: 2^a + 2^b + 1, {} ≤ a ≤ {}".format(a0, args.weight3), "open",
         [(1 << a) + (1 << b) + 1 for a in range(a0, args.weight3 + 1) for b in range(1, a)]),
        ("weight 5, {} bits".format(h), "open", [random_weight(h, 5, rng) for _ in range(n)]),
        ("weight {} of {} bits".format(h // 2, h), "Drmota-Mauduit-Rivat",
         [random_weight(h, h // 2, rng) for _ in range(n)]),
        ("no '11' (fibbinary), {} bits".format(h), "open", [random_fibbinary(h, rng) for _ in range(n)]),
        ("binary palindromes, {} bits".format(h | 1), "open", [random_palindrome(h | 1, rng) for _ in range(n)]),
        ("binary palindromes, {} bits".format(h & ~1), "control: all ÷ 3",
         [random_palindrome(h & ~1, rng) for _ in range(n)]),
        ("n² − 1, n even, {} bits".format(h), "negative control",
         [m * m - 1 for m in ((rng.getrandbits(h // 2) | 1 << (h // 2 - 1)) & ~1 for _ in range(n))]),
    ]


def cmd_unexplored(args):
    rng = random.Random(args.seed)
    sieve_primes = small_primes(args.bound)
    weight = sieve_weight(tuple(sieve_primes))
    print("Sieve random model with every prime ≤ {} (W = {:.2f}), counted with Miller-Rabin".format(
        args.bound, weight))
    print("(probabilistic above 3.3·10^24, error < 4^-13 per number). For every property: observed")
    print("primes against the model's expectation, deviation z in σ.")
    print("Only |z| > 4 counts as structure beyond the model.\n")

    print("A) Windows of {} numbers from a random start in [h, 2h), seed {}.".format(args.width, args.seed))
    print("   Expectation: prime number theorem (window / ln x), spread evenly over the sieve survivors.")
    print("   The equidistributions are proven for whole ranges [1, x]; in short windows at large")
    print("   heights, to my knowledge, they are not.\n")
    print("  {:<8} {:>6} {:>13} {:>9} {:>10}{}".format(
        "h", "u", "surv./Mertens", "primes", "obs./PNT",
        "".join("{:>11}".format(short) for _, short, _ in WINDOW_PROPERTIES)))
    worst = {name: 0.0 for name, _, _ in WINDOW_PROPERTIES}
    starts = []
    for label in args.heights:
        h = parse_height(label)
        start = h + rng.randrange(h)
        starts.append((label, start))
        survivors = window_survivors(start, args.width, sieve_primes)
        flags = [miller_rabin(c) for c in survivors]
        # Not W/ln c: at small u the number of survivors departs from the Mertens product (Buchstab)
        scale = args.width / len(survivors)
        pis = [min(scale / math.log(c), 0.999) for c in survivors]
        u = math.log(start) / math.log(args.bound)
        mertens = len(survivors) / (args.width / weight)
        zs, ratio = [], 0.0
        for name, _, prop in WINDOW_PROPERTIES:
            observed = expected = variance = 0.0
            for c, flag, pi in zip(survivors, flags, pis):
                if prop(c):
                    observed += flag
                    expected += pi
                    variance += pi * (1 - pi)
            z = z_score(observed, expected, variance)
            zs.append(z)
            if abs(z) > abs(worst[name]):
                worst[name] = z
            if name == WINDOW_PROPERTIES[0][0]:
                ratio = observed / expected
        print("  {:<8} {:>6.1f} {:>13.4f} {:>9} {:>10.4f}{}".format(
            label, u, mertens, sum(flags), ratio, "".join("{:>+10.1f}σ".format(z) for z in zs)))
    print("\n  Columns: " + "; ".join("{} = {}".format(short, name) for name, short, _ in WINDOW_PROPERTIES))
    print("  surv./Mertens = sieve survivors / (window · Π(1 − 1/p)); departs from 1 at small")
    print("  u = ln x / ln {} (Buchstab function, known since 1937) -- hence the alignment with the PNT.".format(
        args.bound))
    print("  Starting points (to recompute):")
    for label, start in starts:
        print("    {:<8} {}".format(label, start))
    for name, _, _ in WINDOW_PROPERTIES:
        record("7 Unexplored ranges", "A: " + name, "max. dev.", "{:+.1f} σ".format(worst[name]),
               "noise: < 4 σ", verdict_z(worst[name]))

    print("\nB) Thin binary sets at large heights ({} random samples per set), expectation Σ W/ln s".format(
        args.samples))
    print("   over the sieve survivors; only numbers from {} bits on (u ≥ 4), so the Mertens product holds.\n".format(
        min_bits(args.bound)))
    print("  {:<38} {:<22} {:>9} {:>10} {:>9} {:>10} {:>8}".format(
        "set", "status", "elements", "survive", "measured", "expected", "z"))
    for name, status, elements in thin_sets(args, rng):
        observed, expected, z, survivors = model_test(elements, args.bound, weight)
        print("  {:<38} {:<22} {:>9} {:>10} {:>9.0f} {:>10.1f} {:>+7.1f}σ  {}".format(
            name, status, len(elements), survivors, observed, expected, z, verdict_z(z)))
        record("7 Unexplored ranges", "B: " + name, "meas. (z)", "{:.0f} ({:+.1f} σ)".format(observed, z),
               "model: {:.1f}".format(expected), verdict_z(z))
    print("\n-> The negative control shows: real structure the sieve cannot see ((n−1)(n+1)) stands out at once.")
    print("   Everything else follows the sieve random model at these heights -- as far as the data reaches.")


# ---------------------------------------------------------------------------
# Full run and comparison
# ---------------------------------------------------------------------------

DEMO_COMMANDS = [["table"], ["weights"], ["check", "49"], ["check", "1000003"], ["wheel"], ["bits"], ["rns"]]
BENCH_COMMANDS = ["predict", "ramanujan", "compress", "bias", "zeta", "poly", "learn", "nextprime", "unexplored"]


def run_sections(args, quiet):
    """Every experiment with its own defaults, --limit and --k taken from the call."""
    RESULTS.clear()
    sections = ([] if quiet else DEMO_COMMANDS) + [[name] for name in BENCH_COMMANDS]
    for argv in sections:
        ns = args.parser.parse_args(argv)
        if hasattr(ns, "limit") and argv[0] != "table":
            ns.limit = args.limit
        if argv[0] in BENCH_COMMANDS and hasattr(ns, "k"):
            ns.k = args.k
        if quiet:
            print("running: {} ...".format(argv[0]), file=sys.stderr)
            with contextlib.redirect_stdout(io.StringIO()):
                ns.func(ns)
        else:
            print("=" * 90)
            ns.func(ns)
            print()
    print("=" * 90)
    print_results()


def cmd_all(args):
    run_sections(args, quiet=False)


def cmd_compare(args):
    run_sections(args, quiet=True)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Primes as bit vectors and bit fields, and a test bench for predicting them")
    sub = parser.add_subparsers(dest="cmd")

    def bench_parser(name, help_text, func):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--limit", type=int, default=1_000_000)
        p.add_argument("--k", type=int, default=6, help="number of small prime divisors in the wheel")
        p.set_defaults(func=func)
        return p

    p = sub.add_parser("table", help="show primes as a bit matrix")
    p.add_argument("--limit", type=int, default=64)
    p.set_defaults(func=cmd_table)

    p = sub.add_parser("weights", help="weight matrix 2^j mod p and its periods")
    p.add_argument("--max-p", type=int, default=31)
    p.add_argument("--width", type=int, default=12)
    p.set_defaults(func=cmd_weights)

    p = sub.add_parser("check", help="primality test of one number through bit weights only")
    p.add_argument("n", type=int)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("wheel", help="sieve as an AND of periodic bit masks")
    p.add_argument("--limit", type=int, default=1_000_000)
    p.add_argument("--k", type=int, default=7, help="number of small prime divisors")
    p.set_defaults(func=cmd_wheel)

    p = sub.add_parser("bits", help="statistics of the bit positions of primes")
    p.add_argument("--limit", type=int, default=1_000_000)
    p.add_argument("--low", type=int, default=4, help="number of low bits")
    p.set_defaults(func=cmd_bits)

    p = sub.add_parser("rns", help="numbers in the residue number system, odometer to the next prime")
    p.add_argument("--start", type=int, default=89)
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--next", type=int, default=1327, help="starting value for the odometer")
    p.set_defaults(func=cmd_rns)

    bench_parser("predict", "predict the next prime with own features", cmd_predict)

    p = bench_parser("ramanujan", "Ramanujan filter bank and prediction through Ramanujan sums", cmd_ramanujan)
    p.add_argument("--q", type=int, nargs="+", default=[13, 19, 31, 61, 100], help="truncation bounds Q")

    bench_parser("compress", "1 compression test: is there a pattern beyond the sieve?", cmd_compress)
    bench_parser("bias", "2 Lemke Oliver-Soundararajan bias of consecutive primes", cmd_bias)

    p = bench_parser("zeta", "3 Riemann zeros: peaks, window counts, density", cmd_zeta)
    p.add_argument("--zeros", type=int, nargs="+", default=[10, 50, 100, 200, 300], help="numbers of zeros K")
    p.add_argument("--window", type=int, default=10000, help="window width for the count")

    p = sub.add_parser("poly", help="4 prime density on polynomials (Bateman-Horn)")
    p.add_argument("--n", type=int, default=20000, help="test f(1)..f(N)")
    p.add_argument("--bound", type=int, default=100000, help="primes for the product C_f")
    p.set_defaults(func=cmd_poly)

    p = bench_parser("learn", "5 logistic regression: bits against the residue vector", cmd_learn)
    p.add_argument("--epochs", type=int, default=2)

    p = bench_parser("nextprime", "6 next prime through sieve + Miller-Rabin", cmd_nextprime)
    p.add_argument("--runs", type=int, default=20, help="searches per magnitude")

    p = sub.add_parser("unexplored", help="7 binary patterns at large heights and in thin binary sets")
    p.add_argument("--heights", nargs="+", default=["2^40", "2^64", "10^25", "2^100", "10^50", "2^200"])
    p.add_argument("--width", type=int, default=1 << 20, help="window width in numbers")
    p.add_argument("--bound", type=int, default=10000, help="sieve bound of the model")
    p.add_argument("--bits", type=int, default=200, help="bit length of the samples in part B")
    p.add_argument("--samples", type=int, default=50000, help="sample size per set in part B")
    p.add_argument("--weight3", type=int, default=400, help="largest exponent a in 2^a + 2^b + 1")
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=cmd_unexplored)

    for name, func, text in (("all", cmd_all, "everything with output, the comparison table at the end"),
                             ("compare", cmd_compare, "every experiment quietly, only the comparison table")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--limit", type=int, default=1_000_000)
        p.add_argument("--k", type=int, default=6, help="number of small prime divisors in the wheel")
        p.set_defaults(func=func)
    return parser


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd is None:
        args = parser.parse_args(["all"])
    args.parser = parser
    args.func(args)


if __name__ == "__main__":
    main()
