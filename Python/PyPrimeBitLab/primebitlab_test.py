#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
#
# SPDX-License-Identifier: Apache-2.0

r"""The building blocks every experiment in primebitlab.py stands on, checked against slow truth.

A BENCH IS ONLY AS GOOD AS ITS GROUND TRUTH. Every comparison in primebitlab.py ends in "better",
"worse" or "explained by the model", and each of those words silently trusts the sieve bit field,
Miller-Rabin and the sieve random model. So each is checked here against something that is too
slow for the experiments but cannot be wrong: trial division, gcd with the primorial, brute
force over residues, the direct sum of the Ramanujan sums.

The bench itself has a control that must hold exactly: the candidate model with no feature has to
reproduce the plain wheel. If it ever does not, every 'better' in the comparison table is suspect.

    python primebitlab_test.py
"""

import math
import random
import unittest

import primebitlab as pbl


class BitFieldSieve(unittest.TestCase):
    def test_the_prime_field_is_trial_division(self):
        primes = set(pbl.set_bits(pbl.prime_field(20000)))
        self.assertEqual(primes, {n for n in range(20001) if pbl.is_prime(n)})

    def test_small_primes_is_the_same_list(self):
        self.assertEqual(pbl.small_primes(5000), sorted(n for n in range(5001) if pbl.is_prime(n)))

    def test_a_candidate_field_keeps_exactly_the_numbers_coprime_to_the_divisors(self):
        divisors = (2, 3, 5, 7)
        field = set(pbl.set_bits(pbl.candidate_field(1000, divisors)))
        expected = {n for n in range(2, 1001) if all(n % p for p in divisors)} | set(divisors)
        self.assertEqual(field, expected)

    def test_a_stride_mask_marks_offset_offset_plus_p_and_so_on(self):
        for p, offset, length in ((2, 0, 9), (3, 1, 20), (7, 6, 50), (11, 3, 5), (13, 40, 30)):
            self.assertEqual(pbl.set_bits(pbl.stride_mask(p, offset, length)), list(range(offset, length, p)))

    def test_window_survivors_are_what_the_gcd_with_the_primorial_says(self):
        """Far from 0 the window cannot be checked by trial division -- but the gcd is exact."""
        sieve = pbl.small_primes(1000)
        M = pbl.primorial(1000)
        start = 2 ** 40 + 123457
        survivors = pbl.window_survivors(start, 1 << 14, sieve)
        self.assertEqual(survivors, [c for c in range(start, start + (1 << 14)) if math.gcd(c, M) == 1])


class BitWeights(unittest.TestCase):
    def test_n_mod_p_from_the_set_bits_alone(self):
        rng = random.Random(1)
        for _ in range(300):
            n, p = rng.randrange(1, 1 << 40), rng.choice(pbl.small_primes(200))
            self.assertEqual(pbl.mod_via_bits(n, p)[0], n % p)

    def test_the_period_of_the_weight_vector_is_the_order_of_two(self):
        for p in pbl.small_primes(200)[1:]:
            k = pbl.order_of_two(p)
            self.assertEqual(pow(2, k, p), 1)
            self.assertTrue(all(pow(2, j, p) != 1 for j in range(1, k)))


class MillerRabin(unittest.TestCase):
    def test_it_agrees_with_the_bit_field_up_to_100000(self):
        primes = set(pbl.set_bits(pbl.prime_field(100000)))
        self.assertEqual([n for n in range(100001) if pbl.miller_rabin(n) != (n in primes)], [])

    def test_carmichael_numbers_are_composite(self):
        """They fool the Fermat test for every coprime base; Miller-Rabin must not be fooled."""
        for n in (561, 1105, 1729, 2465, 2821, 6601, 8911, 41041, 825265):
            self.assertEqual(pow(2, n - 1, n), 1)
            self.assertFalse(pbl.miller_rabin(n))

    def test_known_large_primes_and_composites(self):
        for e in (61, 89, 107, 127, 521):
            self.assertTrue(pbl.miller_rabin(2 ** e - 1))
        self.assertFalse(pbl.miller_rabin(2 ** 128 + 1))          # Fermat number F7
        self.assertFalse(pbl.miller_rabin((2 ** 61 - 1) * (2 ** 89 - 1)))

    def test_next_prime_after_a_known_gap_and_a_large_start(self):
        sieve = pbl.small_primes(1000)
        self.assertEqual(pbl.next_prime(1327, sieve)[0], 1361)
        self.assertEqual(pbl.next_prime(10 ** 30, sieve)[0], 10 ** 30 + 57)


class NumberTheory(unittest.TestCase):
    def test_the_ramanujan_product_formula_is_the_direct_sum(self):
        moduli = pbl.small_primes(30)
        masks = pbl.divisor_masks(400, moduli)
        score = pbl.hardy_score(30, moduli)
        for n in range(2, 400):
            direct = sum(pbl.mobius(q) / pbl.euler_phi(q) * pbl.ramanujan_sum(q, n) for q in range(1, 31))
            self.assertAlmostEqual(score(masks[n]), direct, places=9)

    def test_the_ramanujan_sum_is_the_cosine_sum(self):
        for q in range(1, 25):
            for n in range(0, 30):
                cosines = sum(math.cos(2 * math.pi * k * n / q) for k in range(1, q + 1) if math.gcd(k, q) == 1)
                self.assertAlmostEqual(pbl.ramanujan_sum(q, n), cosines, places=9)

    def test_polynomial_roots_mod_p_by_brute_force(self):
        for _name, f in pbl.POLYNOMIALS:
            a, b, c = f
            for p in pbl.small_primes(200):
                brute = sum((a * n * n + b * n + c) % p == 0 for n in range(p))
                self.assertEqual(pbl.poly_roots_mod(f, p), brute, (f, p))

    def test_the_first_zeta_zeros(self):
        zeros, _height, _found = pbl.zeta_zeros(5)
        for got, known in zip(zeros, (14.134725, 21.022040, 25.010858, 30.424876, 32.935062)):
            self.assertAlmostEqual(got, known, delta=0.01)

    def test_the_zero_count_matches_riemann_von_mangoldt(self):
        _zeros, height, found = pbl.zeta_zeros(100)
        self.assertLess(abs(found - (pbl.rs_theta(height) / math.pi + 1)), 2)


class Bench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = pbl.bench(60000)

    def test_THE_CANDIDATE_MODEL_WITHOUT_A_FEATURE_IS_THE_PLAIN_WHEEL(self):
        """The control of every 'better' in the comparison table."""
        prob = pbl.train_candidate_model(lambda p, c: None, self.b)
        self.assertEqual(pbl.candidate_hits(prob, self.b) / len(self.b.test), self.b.baseline)

    def test_and_it_costs_what_the_sieve_random_model_costs(self):
        prob = pbl.train_candidate_model(lambda p, c: None, self.b)
        self.assertLess(abs(pbl.candidate_bits(prob, self.b) / self.b.ref_bits - 1), 0.005)

    def test_real_sieve_knowledge_is_seen_as_better(self):
        """The positive control: a bench that cannot see this cannot see anything."""
        prob = pbl.train_candidate_model(lambda p, c: (c % 17 == 0, c % 19 == 0), self.b)
        rate = pbl.candidate_hits(prob, self.b) / len(self.b.test)
        self.assertEqual(pbl.verdict_hits(rate, self.b.baseline, len(self.b.test)), "better")

    def test_training_and_test_do_not_overlap(self):
        self.assertLess(self.b.train[-1][2], self.b.test[0][2])


class Generators(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(5)

    def test_random_weight_has_exactly_that_many_ones(self):
        for _ in range(200):
            n = pbl.random_weight(64, 7, self.rng)
            self.assertEqual((n.bit_length(), pbl.popcount(n), n & 1), (64, 7, 1))

    def test_random_fibbinary_has_no_adjacent_ones(self):
        for _ in range(200):
            n = pbl.random_fibbinary(64, self.rng)
            self.assertEqual((n.bit_length(), n & (n >> 1), n & 1), (64, 0, 1))

    def test_random_palindrome_reads_the_same_both_ways(self):
        for bits in (31, 32):
            for _ in range(100):
                s = bin(pbl.random_palindrome(bits, self.rng))[2:]
                self.assertEqual((len(s), s), (bits, s[::-1]))

    def test_an_even_length_binary_palindrome_is_divisible_by_three(self):
        """What the 'control: all ÷ 3' row in the unexplored experiment relies on."""
        for _ in range(100):
            self.assertEqual(pbl.random_palindrome(40, self.rng) % 3, 0)

    def test_parse_height(self):
        self.assertEqual([pbl.parse_height(t) for t in ("2^64", "10^25", "12345")], [2 ** 64, 10 ** 25, 12345])


if __name__ == "__main__":
    unittest.main(verbosity=2)
