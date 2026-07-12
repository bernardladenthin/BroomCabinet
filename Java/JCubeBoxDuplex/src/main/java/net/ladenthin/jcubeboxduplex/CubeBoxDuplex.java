// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

/*
 * Cube-Box Duplex (CBD) — experimental symmetric forward-only cipher.
 *
 * EXPERIMENTAL / EDUCATIONAL. This construction has NOT undergone public
 * cryptanalysis. Do not use it to protect real data. See SPEC.md.
 */
package net.ladenthin.jcubeboxduplex;

import java.util.Arrays;

/**
 * Reference implementation of the Cube-Box Duplex (CBD).
 *
 * <p>Design highlights (see {@code SPEC.md} for the full specification):
 * <ul>
 *   <li><b>Forward-only:</b> encryption and decryption both run the same
 *       keyed permutation {@code P} forwards. There is no inverse permutation.
 *   <li><b>Cube-box choice stream:</b> in every round each 64-bit lane is
 *       transformed by one of {@value #NUM_BOXES} bijective "cube boxes"; the
 *       index is chosen data- and key-dependently, so the sequence of box
 *       choices is a secret stream driven by the key.
 *   <li><b>All-or-Nothing + anchor:</b> plaintext feedback chains every block
 *       into the state, and the initial state is seeded from the first
 *       plaintext block. Decryption therefore <i>requires</i> that first block
 *       (the "anchor") in addition to the key and nonce.
 *   <li><b>Work factor:</b> a tunable number of permutation applications per
 *       block ({@code W}); a symmetric hardness knob (both sides pay it).
 *   <li><b>Quantum margin:</b> 512-bit state, no algebraic trapdoor; only
 *       Grover applies, which merely halves the security level.
 * </ul>
 */
public final class CubeBoxDuplex {

    /** Number of 64-bit lanes in the state (512-bit state). */
    public static final int LANES = 8;
    /** Number of lanes forming the rate (256-bit rate). */
    public static final int RATE_LANES = 4;
    /** Block size in bytes (rate in bytes). */
    public static final int BLOCK_BYTES = RATE_LANES * Long.BYTES; // 32
    /** Number of rounds in the permutation {@code P}. */
    public static final int ROUNDS = 12;
    /** Number of cube boxes (a 4-bit selector). */
    public static final int NUM_BOXES = 16;
    /** Authentication tag length in bytes. */
    public static final int TAG_BYTES = 16;
    /** Required nonce length in bytes. */
    public static final int NONCE_BYTES = 16;

    // -- nothing-up-my-sleeve constants, derived deterministically from a seed --
    private static final long[] BOX_MUL = new long[NUM_BOXES];
    private static final int[] BOX_ROT = new int[NUM_BOXES];
    private static final long[] BOX_ADD = new long[NUM_BOXES];
    private static final int RC_LEN = 128;
    private static final long[] RC = new long[RC_LEN];

    // domain-separation constants for the internal sponge hash
    private static final long DOMAIN_KEY = 0x4B45592D53434845L; // "KEY-SCHE"
    private static final long DOMAIN_HASH = 0x484153482D2D2D2DL; // "HASH----"
    private static final long TAG_DOMAIN = 0x8000000000000000L;

    static {
        long[] sm = {0x9E3779B97F4A7C15L}; // documented SplitMix64 seed
        for (int i = 0; i < NUM_BOXES; i++) {
            BOX_MUL[i] = splitmix64(sm) | 1L; // odd -> multiply is a bijection mod 2^64
            int rot = (int) (splitmix64(sm) & 63L);
            BOX_ROT[i] = rot == 0 ? 1 : rot;
            BOX_ADD[i] = splitmix64(sm);
        }
        for (int i = 0; i < RC_LEN; i++) {
            RC[i] = splitmix64(sm);
        }
    }

    private static final long[] ZERO_KEY = new long[LANES];

    private final int workFactor;

    /**
     * Creates a CBD instance.
     *
     * @param workFactor number of permutation applications per block ({@code >= 1})
     */
    public CubeBoxDuplex(int workFactor) {
        if (workFactor < 1) {
            throw new IllegalArgumentException("workFactor must be >= 1");
        }
        this.workFactor = workFactor;
    }

    // ------------------------------------------------------------------
    // Primitives
    // ------------------------------------------------------------------

    private static long splitmix64(long[] state) {
        long z = (state[0] += 0x9E3779B97F4A7C15L);
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    /** One cube box: a bijection on 64 bits. */
    private static long box(int idx, long x) {
        return Long.rotateLeft(x * BOX_MUL[idx], BOX_ROT[idx]) ^ BOX_ADD[idx];
    }

    /** Keyed forward permutation {@code P} over the 512-bit state (in place). */
    private static void permute(long[] st, long[] keyLanes) {
        final int[] sel = new int[LANES];
        final long[] t = new long[LANES];
        for (int r = 0; r < ROUNDS; r++) {
            // 1. cube-box layer: data- and key-dependent box selection (choice stream)
            for (int j = 0; j < LANES; j++) {
                long src = (st[(j + 1) & 7] >>> 5)
                        ^ (st[(j + 5) & 7] >>> 33)
                        ^ RC[(r * LANES + j) & (RC_LEN - 1)]
                        ^ keyLanes[j];
                sel[j] = (int) (src & (NUM_BOXES - 1));
            }
            for (int j = 0; j < LANES; j++) {
                st[j] = box(sel[j], st[j]);
            }
            // 2. linear diffusion across lanes
            for (int j = 0; j < LANES; j++) {
                t[j] = st[j]
                        ^ Long.rotateLeft(st[(j + 7) & 7], 7)
                        ^ Long.rotateLeft(st[(j + 2) & 7], 31);
            }
            // 3. positional lane rotation by 3 + round constant
            for (int j = 0; j < LANES; j++) {
                st[j] = t[(j + 3) & 7] ^ RC[(r + j) & (RC_LEN - 1)];
            }
        }
    }

    // ------------------------------------------------------------------
    // Sponge hash / key schedule (keyless permutation)
    // ------------------------------------------------------------------

    private static long[] spongeHash(byte[] data, long domain) {
        long[] st = new long[LANES];
        st[LANES - 1] ^= domain;
        byte[] padded = pad(data);
        for (int off = 0; off < padded.length; off += BLOCK_BYTES) {
            for (int j = 0; j < RATE_LANES; j++) {
                st[j] ^= readLE(padded, off + j * Long.BYTES);
            }
            permute(st, ZERO_KEY);
        }
        return st;
    }

    private static long[] deriveKeyLanes(byte[] key) {
        return spongeHash(key, DOMAIN_KEY);
    }

    private static long[] hashLanes(byte[] data) {
        return spongeHash(data, DOMAIN_HASH);
    }

    private long[] init(long[] keyLanes, byte[] nonce, byte[] anchorBlock0) {
        long[] st = new long[LANES];
        long[] nl = hashLanes(nonce);
        for (int j = 0; j < LANES; j++) {
            st[j] ^= nl[j];
        }
        permute(st, keyLanes);
        // Absorb the first plaintext block (the anchor). Without it the state is
        // wrong and nothing downstream decrypts -> anchor is mandatory.
        long[] al = hashLanes(anchorBlock0);
        for (int j = 0; j < LANES; j++) {
            st[j] ^= al[j];
        }
        permute(st, keyLanes);
        return st;
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    /**
     * Encrypts {@code plaintext} and returns a self-describing package
     * {@code [len(8) | nonce(16) | ciphertext | tag(16)]}.
     *
     * @param key       secret key (any length)
     * @param nonce     unique nonce, exactly {@value #NONCE_BYTES} bytes
     * @param plaintext data to encrypt
     * @return the encrypted package
     */
    public byte[] encrypt(byte[] key, byte[] nonce, byte[] plaintext) {
        requireNonce(nonce);
        long[] keyLanes = deriveKeyLanes(key);
        int nBlocks = Math.max(1, (plaintext.length + BLOCK_BYTES - 1) / BLOCK_BYTES);
        byte[] block0 = blockOf(plaintext, 0);
        long[] st = init(keyLanes, nonce, block0);

        byte[] ct = new byte[nBlocks * BLOCK_BYTES];
        for (int i = 0; i < nBlocks; i++) {
            byte[] mi = blockOf(plaintext, i);
            for (int j = 0; j < RATE_LANES; j++) {
                long m = readLE(mi, j * Long.BYTES);
                writeLE(ct, i * BLOCK_BYTES + j * Long.BYTES, m ^ st[j]); // keystream = rate
                st[j] ^= m; // plaintext feedback -> all-or-nothing chaining
            }
            st[4] ^= (long) i; // per-block domain separation
            for (int w = 0; w < workFactor; w++) {
                permute(st, keyLanes);
            }
        }
        byte[] tag = finalizeTag(st, keyLanes);

        byte[] pkg = new byte[Long.BYTES + NONCE_BYTES + ct.length + TAG_BYTES];
        writeLE(pkg, 0, (long) plaintext.length);
        System.arraycopy(nonce, 0, pkg, Long.BYTES, NONCE_BYTES);
        System.arraycopy(ct, 0, pkg, Long.BYTES + NONCE_BYTES, ct.length);
        System.arraycopy(tag, 0, pkg, Long.BYTES + NONCE_BYTES + ct.length, TAG_BYTES);
        return pkg;
    }

    /**
     * Decrypts a package produced by {@link #encrypt}.
     *
     * @param key            the secret key
     * @param pkg            the encrypted package
     * @param anchorFirstBytes the first (up to {@value #BLOCK_BYTES}) plaintext
     *                       bytes — the mandatory anchor
     * @return the recovered plaintext
     * @throws SecurityException if the anchor or key is wrong, or the tag fails
     */
    public byte[] decrypt(byte[] key, byte[] pkg, byte[] anchorFirstBytes) {
        long len = readLE(pkg, 0);
        byte[] nonce = Arrays.copyOfRange(pkg, Long.BYTES, Long.BYTES + NONCE_BYTES);
        int ctStart = Long.BYTES + NONCE_BYTES;
        int ctLen = pkg.length - ctStart - TAG_BYTES;
        int nBlocks = ctLen / BLOCK_BYTES;
        byte[] tag = Arrays.copyOfRange(pkg, pkg.length - TAG_BYTES, pkg.length);

        byte[] block0 = new byte[BLOCK_BYTES];
        System.arraycopy(anchorFirstBytes, 0, block0, 0,
                Math.min(BLOCK_BYTES, anchorFirstBytes.length));

        long[] keyLanes = deriveKeyLanes(key);
        long[] st = init(keyLanes, nonce, block0);

        byte[] pt = new byte[nBlocks * BLOCK_BYTES];
        for (int i = 0; i < nBlocks; i++) {
            for (int j = 0; j < RATE_LANES; j++) {
                long c = readLE(pkg, ctStart + i * BLOCK_BYTES + j * Long.BYTES);
                long m = c ^ st[j];
                writeLE(pt, i * BLOCK_BYTES + j * Long.BYTES, m);
                st[j] ^= m;
            }
            st[4] ^= (long) i;
            for (int w = 0; w < workFactor; w++) {
                permute(st, keyLanes);
            }
        }
        // anchor check: recovered first block must match the supplied anchor
        for (int k = 0; k < BLOCK_BYTES; k++) {
            if (pt[k] != block0[k]) {
                throw new SecurityException("anchor or key mismatch");
            }
        }
        byte[] t2 = finalizeTag(st, keyLanes);
        if (!constantTimeEquals(t2, tag)) {
            throw new SecurityException("authentication tag mismatch");
        }
        return Arrays.copyOf(pt, (int) len);
    }

    private static byte[] finalizeTag(long[] st, long[] keyLanes) {
        long[] f = Arrays.copyOf(st, LANES);
        f[LANES - 1] ^= TAG_DOMAIN;
        permute(f, keyLanes);
        byte[] tag = new byte[TAG_BYTES];
        writeLE(tag, 0, f[0]);
        writeLE(tag, 8, f[1]);
        return tag;
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private static void requireNonce(byte[] nonce) {
        if (nonce == null || nonce.length != NONCE_BYTES) {
            throw new IllegalArgumentException("nonce must be " + NONCE_BYTES + " bytes");
        }
    }

    private static byte[] pad(byte[] d) {
        int padded = ((d.length / BLOCK_BYTES) + 1) * BLOCK_BYTES;
        byte[] r = new byte[padded];
        System.arraycopy(d, 0, r, 0, d.length);
        r[d.length] = 0x01; // 10* padding delimiter
        return r;
    }

    private static byte[] blockOf(byte[] data, int i) {
        byte[] b = new byte[BLOCK_BYTES];
        int off = i * BLOCK_BYTES;
        int n = Math.min(BLOCK_BYTES, Math.max(0, data.length - off));
        if (n > 0) {
            System.arraycopy(data, off, b, 0, n);
        }
        return b;
    }

    private static long readLE(byte[] b, int off) {
        long v = 0;
        for (int i = 0; i < Long.BYTES; i++) {
            v |= (b[off + i] & 0xFFL) << (8 * i);
        }
        return v;
    }

    private static void writeLE(byte[] b, int off, long v) {
        for (int i = 0; i < Long.BYTES; i++) {
            b[off + i] = (byte) (v >>> (8 * i));
        }
    }

    private static boolean constantTimeEquals(byte[] a, byte[] b) {
        if (a.length != b.length) {
            return false;
        }
        int diff = 0;
        for (int i = 0; i < a.length; i++) {
            diff |= a[i] ^ b[i];
        }
        return diff == 0;
    }
}
