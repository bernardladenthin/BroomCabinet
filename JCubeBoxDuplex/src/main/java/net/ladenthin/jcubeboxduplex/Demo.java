/*
 * Cube-Box Duplex (CBD) — self-test / demo runner.
 * Copyright 2026 Bernard Ladenthin — Apache License 2.0.
 */
package net.ladenthin.jcubeboxduplex;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/** Runnable self-test that demonstrates and verifies the CBD properties. */
public final class Demo {

    private static int checks;
    private static int failures;

    public static void main(String[] args) {
        CubeBoxDuplex cbd = new CubeBoxDuplex(2); // work factor 2

        byte[] key = "correct horse battery staple".getBytes(StandardCharsets.UTF_8);
        byte[] nonce = new byte[CubeBoxDuplex.NONCE_BYTES];
        for (int i = 0; i < nonce.length; i++) {
            nonce[i] = (byte) (i * 7 + 1);
        }
        byte[] plaintext = ("Cube-Box Duplex: forward-only, quantum-margin, "
                + "anchor-required decryption. Ein Test mit Emoji-Bytes und Umlauten äöü.")
                .getBytes(StandardCharsets.UTF_8);

        byte[] pkg = cbd.encrypt(key, nonce, plaintext);
        byte[] anchor = Arrays.copyOf(plaintext, Math.min(CubeBoxDuplex.BLOCK_BYTES, plaintext.length));

        // 1. round-trip with correct key + anchor
        byte[] recovered = cbd.decrypt(key, pkg, anchor);
        check("round-trip recovers plaintext", Arrays.equals(recovered, plaintext));

        // 2. decryption without the correct first-block anchor must fail
        byte[] badAnchor = anchor.clone();
        badAnchor[0] ^= 0x01;
        check("wrong anchor is rejected", throwsSecurity(() -> cbd.decrypt(key, pkg, badAnchor)));

        // 3. wrong key must fail
        byte[] badKey = key.clone();
        badKey[0] ^= 0x01;
        check("wrong key is rejected", throwsSecurity(() -> cbd.decrypt(badKey, pkg, anchor)));

        // 4. any tampered ciphertext byte must fail (all-or-nothing + tag)
        byte[] tampered = pkg.clone();
        tampered[tampered.length - CubeBoxDuplex.TAG_BYTES - 1] ^= 0x01;
        check("tampered ciphertext is rejected", throwsSecurity(() -> cbd.decrypt(key, tampered, anchor)));

        // 5. keystream diffusion: flipping one NONCE bit changes ~half of ALL
        //    ciphertext bits (the proper avalanche test for a stream cipher —
        //    flipping a plaintext bit only XORs that one bit, as in ChaCha20).
        byte[] nonce2 = nonce.clone();
        nonce2[0] ^= 0x01;
        byte[] pkg3 = cbd.encrypt(key, nonce2, plaintext);
        double frac = bitDiffFraction(ciphertextOf(pkg), ciphertextOf(pkg3));
        check("keystream avalanche near 0.5 (got " + String.format("%.3f", frac) + ")",
                frac > 0.40 && frac < 0.60);

        // 6. different nonce -> different ciphertext for same plaintext
        check("nonce changes ciphertext", !Arrays.equals(ciphertextOf(pkg), ciphertextOf(pkg3)));

        // 7. empty plaintext round-trips
        byte[] emptyPkg = cbd.encrypt(key, nonce, new byte[0]);
        byte[] emptyOut = cbd.decrypt(key, emptyPkg, new byte[0]);
        check("empty plaintext round-trips", emptyOut.length == 0);

        System.out.println();
        System.out.println("checks: " + checks + "  failures: " + failures);
        System.out.println("ciphertext length for " + plaintext.length + "-byte message: "
                + ciphertextOf(pkg).length + " bytes (+ header + tag)");
        if (failures != 0) {
            System.exit(1);
        }
        System.out.println("ALL CHECKS PASSED");
    }

    private static byte[] ciphertextOf(byte[] pkg) {
        int start = Long.BYTES + CubeBoxDuplex.NONCE_BYTES;
        return Arrays.copyOfRange(pkg, start, pkg.length - CubeBoxDuplex.TAG_BYTES);
    }

    private static double bitDiffFraction(byte[] a, byte[] b) {
        int n = Math.min(a.length, b.length);
        int diff = 0;
        for (int i = 0; i < n; i++) {
            diff += Integer.bitCount((a[i] ^ b[i]) & 0xFF);
        }
        return diff / (double) (n * 8);
    }

    private interface Body {
        void run();
    }

    private static boolean throwsSecurity(Body body) {
        try {
            body.run();
            return false;
        } catch (SecurityException e) {
            return true;
        }
    }

    private static void check(String name, boolean ok) {
        checks++;
        if (!ok) {
            failures++;
        }
        System.out.println((ok ? "[PASS] " : "[FAIL] ") + name);
    }
}
