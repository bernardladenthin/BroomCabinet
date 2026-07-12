# Cube-Box Duplex (CBD)

Ein **experimenteller**, quanten-orientierter symmetrischer Vorwärts-Chiffre mit
einer neuartigen Struktureigenschaft: **Entschlüsseln geht vorwärts wie
Verschlüsseln, braucht aber mehr Information** — Schlüssel + Nonce + den *ersten
Klartextblock* als Anker.

> ⚠️ **Nicht für echte Daten.** Ohne öffentliche Kryptoanalyse ist kein selbst
> entworfenes Verfahren vertrauenswürdig. CBD ist ein Design-Experiment. Für
> echte Verschlüsselung: AES-GCM, ChaCha20-Poly1305, oder für post-quantum
> ML-KEM/ML-DSA (FIPS 203/204).

## Die Besonderheit

- **Nur vorwärts** — eine einzige keyed Permutation `P`, kein inverser Operator.
- **Würfel-Box-Auswahlstrom** — jede Runde wählt daten- und schlüsselabhängig
  eine von 16 bijektiven 64-Bit-Boxen; die Wahlsequenz ist geheim.
- **All-or-Nothing + Anker** — der Startzustand wird aus dem ersten Klartextblock
  geseedet; ohne ihn dekodiert nichts.
- **Work-Faktor `W`** — symmetrischer Härte-Regler pro Block.
- **512-Bit-Zustand, keine Falltür** — nur Grover greift → quantensicher-Klasse.

Details und die ehrlichen Grenzen: siehe [`SPEC.md`](SPEC.md).

## Bauen & Testen

Mit Maven (bevorzugt):

```bash
mvn compile exec:java
```

Oder direkt mit dem JDK, ohne Maven:

```bash
javac -d target/classes $(find src -name '*.java')
java -cp target/classes net.ladenthin.jcubeboxduplex.Demo
```

Erwartet: `ALL CHECKS PASSED` (7 Checks, u. a. Round-Trip, Anker-Pflicht,
Manipulations-Ablehnung, Keystream-Avalanche ≈ 0.5).

## Benutzung

```java
CubeBoxDuplex cbd = new CubeBoxDuplex(2);          // Work-Faktor 2
byte[] pkg = cbd.encrypt(key, nonce16, plaintext); // [len|nonce|ciphertext|tag]
byte[] anchor = Arrays.copyOf(plaintext, 32);      // erster Block = Anker
byte[] out = cbd.decrypt(key, pkg, anchor);        // wirft SecurityException bei falschem Anker/Key/Tag
```

## Lizenz

Apache 2.0.
